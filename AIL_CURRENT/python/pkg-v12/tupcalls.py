"""Call lowering of the tuple pass: builtins, heapq, math, list / str / dict / set methods, user functions."""
import ast

from tupcommon import *  # noqa: F401,F403
from tupexpr import unopt


class Calls:
    # ------------------------------------------------------------------------------------------
    def fill(self, hole, t):
        """Settle an unknown element type once something of that type goes in."""
        t = deep(t)
        if isinstance(hole, Hole) and R(hole) is None and t is not None and t != 'none':
            hole.t = t

    def args_ex(self, node, wants=None, ctx=None):
        """Lower positional arguments (with wanted types) and keyword values; returns (args, types, keywords)."""
        args, ts = [], []
        for i, a in enumerate(node.args):
            w = wants[i] if wants and i < len(wants) else None
            if isinstance(a, ast.Starred):
                self.refuse(node, 'a *argument in a call')
            if isinstance(a, ast.Lambda):
                n, t = self.lambda_(a, [])
            else:
                n, t = self.exv(a, w, ctx)
            n, t = self.coerce(n, t, w)
            args.append(n)
            ts.append(t)
        kws = []
        for kw in node.keywords:
            if isinstance(kw.value, ast.Lambda):
                n = self.lambda_(kw.value, [])[0]
            elif (kw.arg == 'separators' and isinstance(kw.value, ast.Tuple)
                  and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in kw.value.elts)):
                # json.dumps(separators=(",", ":")): the json lowering reads this literal pair itself
                n = kw.value
            else:
                n, _ = self.exv(kw.value)
            kws.append(ast.keyword(arg=kw.arg, value=n))
        return args, ts, kws

    def done(self, node, args, kws, t):
        node.args, node.keywords = args, kws
        return node, t

    def no_tuple_items(self, node, ts, what):
        """A builtin that iterates its argument was given a tuple: the tuple is a class here, which the
        generic runtime cannot iterate (`sum(c)`, `list(c)`, `any(c)`, `set(c)` ... ended in a TypeError)."""
        if what in ('str.format', 'str.join') or what in self.ITERATING:
            for t in ts:
                if is_tuple(deep(t)):
                    self.refuse(node, '%s() of a tuple (iterating a tuple is not built); unpack it or name '
                                'the items' % what.replace('str.', ''))

    ITERATING = {'sum', 'any', 'all', 'list', 'set', 'frozenset', 'dict', 'reversed', 'enumerate', 'zip',
                 'map', 'filter', 'next', 'iter', 'sorted', 'min', 'max', 'tuple', 'str.join'}

    def ex_Call(self, node, want=None, ctx=None):
        f = node.func
        if isinstance(f, ast.Name):
            nm = f.id
            if nm in self.lam_alias:
                return self.call_alias(node, self.lam_alias[nm])
            if nm in self.alias or nm in self.env:
                return self.generic_call(node)
            if nm in self.funcs:
                return self.call_user(node, self.funcs[nm])
            if nm in self.classes:
                return self.call_ctor(node, nm)
            if nm in self.fromnames:
                return self.call_module(node, self.fromnames[nm][0], self.fromnames[nm][1], want)
            handler = getattr(self, 'b_' + nm, None)
            if handler is not None:
                return handler(node, want, ctx)
            return self.generic_call(node)
        if isinstance(f, ast.Attribute):
            if isinstance(f.value, ast.Name) and f.value.id in self.modalias and f.value.id not in self.env:
                return self.call_module(node, self.modalias[f.value.id], f.attr, want)
            return self.call_method(node, want)
        return self.generic_call(node)

    def generic_call(self, node):
        if not isinstance(node.func, ast.Name):
            node.func = self.exv(node.func)[0]
        args, ts, kws = self.args_ex(node)
        if isinstance(node.func, ast.Name):
            self.no_tuple_items(node, ts, node.func.id)
        return self.done(node, args, kws, None)

    # ------------------------------------------------------------------------------------------
    # user functions and classes
    def call_user(self, node, sig):
        method = isinstance(node.func, ast.Attribute) and sig.owner
        params = sig.params[1:] if method else sig.params
        clone, extra = None, []
        fixed = {}                                  # argument index -> replacement (a lifted lambda's name)
        for i, a in enumerate(node.args):
            if i < len(params) and isinstance(a, (ast.Lambda, ast.Name)):
                r = self.lam_arg(sig, i + (1 if method else 0), a, node)
                if r is None:
                    continue
                repl, caps, cl = r
                if cl is not None:
                    if clone is not None:
                        self.refuse(node, 'two lambdas with captures in one call')
                    clone, extra = cl, caps
                    fixed[i] = None
                else:
                    fixed[i] = repl
        keep = [i for i in range(len(node.args)) if fixed.get(i, 0) is not None]
        wants = [params[i][1] if i < len(params) else None for i in keep]
        sub_args = [node.args[i] for i in keep]
        args, ts, _ = self.args_ex(ast.Call(func=node.func, args=[
            ast.Constant(value=0) if i in fixed else node.args[i] for i in keep], keywords=[]), wants)
        for j, i in enumerate(keep):
            if i in fixed:
                args[j] = fixed[i]
        kws = []
        for kw in node.keywords:
            w = next((p[1] for p in sig.params if p[0] == kw.arg), None)
            if isinstance(kw.value, (ast.Lambda, ast.Name)) and isinstance(deep(w), tuple) \
                    and deep(w)[0] == 'callable':
                pi = next(i for i, p in enumerate(sig.params) if p[0] == kw.arg)
                r = self.lam_arg(sig, pi, kw.value, node)
                if r is not None:
                    repl, caps, cl = r
                    if cl is not None:
                        self.refuse(node, 'a lambda with captures passed by keyword; pass it positionally')
                    kws.append(ast.keyword(arg=kw.arg, value=repl))
                    continue
            n, t = self.exv(kw.value, w)
            n, t = self.coerce(n, t, w)
            kws.append(ast.keyword(arg=kw.arg, value=n))
        t = sig.ret
        if is_tuple(t):
            self.force()
        if clone is not None:
            return ast.Call(func=name(clone), args=extra + args, keywords=kws), t
        return self.done(node, args, kws, t)

    def call_ctor(self, node, cname):
        fields = self.ctor_fields.get(cname, [])
        args, ts, kws = self.args_ex(node, [f[1] for f in fields])
        return self.done(node, args, kws, ('cls', cname))

    # ------------------------------------------------------------------------------------------
    # builtins
    def b_len(self, node, want, ctx):
        if len(node.args) != 1 or node.keywords:
            return self.generic_call(node)
        if self.is_rowconst(node.args[0]):
            self.force()
            return call('len', name(node.args[0].id + '__c0')), INT
        n, t = self.exv(node.args[0])
        t = deep(t)
        if is_table(t):
            self.force()
            return attr(n, 'n'), INT
        if is_tuple(t):
            self.force()
            return const(len(t[1])), INT
        return self.done(node, [n], [], INT)

    def printable(self, n, t, node):
        """A value being turned into text (print, str, f-string): tuples and lists of tuples get their repr."""
        t = deep(t)
        if is_tuple(t) or (isinstance(t, tuple) and t[0] in ('list', 'opt') and has_tuple(t)):
            self.force()
            return call(self.repr_fn(t), n)
        if isinstance(t, tuple) and t[0] == 'list' and known(t):
            try:
                return call(self.repr_fn(t), n)        # print(xs) of plain lists: CPython's repr (forces nothing)
            except Refused:
                return n
        if is_table(t):
            self.refuse(node, 'printing a dict or set holding tuples; print its items one by one')
        return n

    def b_print(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        args = [self.printable(a, t, node) for a, t in zip(args, ts)]
        return self.done(node, args, kws, 'none')

    def b_str(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        if len(args) == 1:
            args = [self.printable(args[0], ts[0], node)]
            if is_tuple(ts[0]):
                return args[0], STR
        return self.done(node, args, kws, STR)

    def b_repr(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        if len(args) != 1:
            return self.done(node, args, kws, STR)
        t = deep(ts[0])
        self.force()
        if t == STR:
            return call(self.gen.srepr(), args[0]), STR
        if t in (INT, FLT, BOOL):
            return call('str', args[0]), STR
        return call(self.repr_fn(t), args[0]), STR

    def b_int(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        return self.done(node, args, kws, INT)

    def b_float(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        return self.done(node, args, kws, FLT)

    def b_bool(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        return self.done(node, args, kws, BOOL)

    def b_ord(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        return self.done(node, args, kws, INT)

    def b_chr(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        return self.done(node, args, kws, STR)

    def b_input(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        return self.done(node, args, kws, STR)

    def b_isinstance(self, node, want, ctx):
        return self.generic_call(node)[0], BOOL

    def b_any(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        self.no_tuple_items(node, ts, 'any')
        return self.done(node, args, kws, BOOL)

    b_all = b_any

    def b_abs(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        return self.done(node, args, kws, deep(ts[0]) if ts else None)

    def b_round(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        return self.done(node, args, kws, INT if len(args) == 1 else FLT)

    def b_sum(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        self.no_tuple_items(node, ts[:1], 'sum')
        et = elem_of(ts[0]) if ts else None
        if len(args) > 1:
            et = deep(ts[1])
        return self.done(node, args, kws, et if et in (INT, FLT, BOOL) else (INT if et is None else et))

    def b_range(self, node, want, ctx):
        args, ts, kws = self.args_ex(node, [INT, INT, INT])
        return self.done(node, args, kws, ('range',))

    def b_reversed(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        self.no_tuple_items(node, ts, 'reversed')
        return self.done(node, args, kws, ('iter', elem_of(ts[0]) if ts else None))

    def b_enumerate(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        self.no_tuple_items(node, ts, 'enumerate')
        return self.done(node, args, kws, ('iter', None))

    def b_zip(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        self.no_tuple_items(node, ts, 'zip')
        if any(has_tuple(elem_of(t)) for t in ts):
            self.refuse(node, 'zip over tuples outside a for loop or comprehension; loop with an index')
        return self.done(node, args, kws, ('iter', None))

    def b_divmod(self, node, want, ctx):
        args, ts, kws = self.args_ex(node)
        if len(args) != 2 or kws:
            self.refuse(node, 'divmod takes two numbers')
        ts = [deep(t) for t in ts]
        if not all(t in NUMERIC for t in ts):
            self.refuse(node, 'divmod of values whose type is not known to be int or float')
        self.force()
        if FLT in ts:
            args = [self.coerce(a, t, FLT)[0] for a, t in zip(args, ts)]
            return call(self.gen.divmod(True), *args), ('tuple', (FLT, FLT))
        return call(self.gen.divmod(False), *args), ('tuple', (INT, INT))

    def b_list(self, node, want, ctx):
        if not node.args:
            w = deep(want)
            we = w[1] if isinstance(w, tuple) and w[0] == 'list' else None
            return self.done(node, [], [], ('list', we if we is not None else Hole()))
        n, t = self.exv(node.args[0])
        t = deep(t)
        self.no_tuple_items(node, [t], 'list')
        if is_table(t):
            self.force()
            return call(self.table(t).fn('keys'), n), ('list', t[1])
        return self.done(node, [n], [], ('list', elem_of(t)))

    def b_set(self, node, want, ctx):
        w = deep(want)
        we = w[1] if isinstance(w, tuple) and w[0] == 'set' else None
        if not node.args:
            t = ('set', we if we is not None else Hole())
            if is_table_set(t):
                self.force()
                return call(self.table(t).fn('new')), t
            return self.done(node, [], [], t)
        n, t = self.exv(node.args[0])
        t = deep(t)
        self.no_tuple_items(node, [t], 'set')
        et = elem_of(t)
        st = ('set', et if et is not None else we)
        if is_table_set(st):
            self.force()
            tbl = self.table(st)
            if is_table_set(t):
                return call(tbl.fn('copy'), n), st
            if isinstance(t, tuple) and t[0] == 'list':
                return call(tbl.fn('fromlist'), n), st
            self.refuse(node, 'set(...) of something other than a list of tuples; build a list first')
        return self.done(node, [n], [], st)

    def b_dict(self, node, want, ctx):
        w = deep(want)
        wk, wv = (w[1], w[2]) if isinstance(w, tuple) and w[0] == 'dict' else (None, None)
        if not node.args and not node.keywords:
            t = ('dict', wk if wk is not None else Hole(), wv if wv is not None else Hole())
            if is_table_dict(t):
                self.force()
                return call(self.table(t).fn('new')), t
            return self.done(node, [], [], t)
        if len(node.args) == 1 and not node.keywords:
            n, t = self.exv(node.args[0])
            t = deep(t)
            self.no_tuple_items(node, [t], 'dict')
            if is_table_dict(t):
                self.force()
                return call(self.table(t).fn('copy'), n), t
            if isinstance(t, tuple) and t[0] == 'list' and is_tuple(t[1]) and len(t[1][1]) == 2:
                dt = ('dict', t[1][1][0], t[1][1][1])
                if not is_table_dict(dt):
                    self.refuse(node, 'dict(list of pairs) of plain keys and values; build it with a loop')
                self.force()
                return call(self.table(dt).fn('dfromlist'), n), dt
            return self.done(node, [n], [], ('dict', None, None))
        return self.generic_call(node)

    def b_tuple(self, node, want, ctx):
        self.refuse(node, 'tuple(...) (a tuple of a run-time length); spell the elements (a, b)')

    def b_frozenset(self, node, want, ctx):
        return self.b_set(node, want, ctx)

    # -- sorting ------------------------------------------------------------------------------------
    def default_key(self, et, node):
        lv = leaves(et, '_k')
        if len(lv) > 4:
            self.refuse(node, 'ordering tuples with more than 4 scalar fields in one call is not built here '
                        '(list.sort() on a list of them is)')
        if len(lv) == 1:
            body = ast.parse(lv[0][0] if lv[0][1] != BOOL else 'int(%s)' % lv[0][0], mode='eval').body
        else:
            body = ast.parse('(%s)' % ', '.join(p if t != BOOL else 'int(%s)' % p for p, t in lv),
                             mode='eval').body
        return ast.Lambda(args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='_k')], kwonlyargs=[],
                                             kw_defaults=[], defaults=[]), body=body)

    def key_kw(self, node, kws, et):
        """The key= keyword of a sort / heap call: the user's lambda lowered over the element type, or the
        default tuple order."""
        out, has_key = [], False
        for kw in node.keywords:
            if kw.arg == 'key' and isinstance(kw.value, ast.Name) and kw.value.id in self.lam_alias:
                kw = ast.keyword(arg='key', value=fresh_copy(self.lam_alias[kw.value.id].node))
            if kw.arg == 'key':
                has_key = True
                if isinstance(kw.value, ast.Lambda):
                    self.quiet += 1
                    try:
                        lam = self.lambda_(kw.value, [et], 'key')[0]
                    finally:
                        self.quiet -= 1
                    out.append(ast.keyword(arg='key', value=lam))
                else:
                    out.append(ast.keyword(arg='key', value=self.exv(kw.value)[0]))
            else:
                out.append(ast.keyword(arg=kw.arg, value=self.exv(kw.value)[0]))
        if not has_key and is_tuple(et):
            out.append(ast.keyword(arg='key', value=self.default_key(et, node)))
        return out

    def b_sorted(self, node, want, ctx):
        if not node.args:
            return self.generic_call(node)
        src, st, _ = self.iter_source(node.args[0])
        src, st = self.realize(src, st)
        st = deep(st)
        et = elem_of(st)
        if is_tuple(st):
            self.refuse(node, 'sorted() of a tuple')
        kws = self.key_kw(node, node.keywords, et)
        return self.done(node, [src], kws, ('list', et))

    def minmax(self, node, op):
        pair_ts = []
        if len(node.args) == 1 and not any(kw.arg == 'key' for kw in node.keywords):
            n, t = self.exv(node.args[0])
            t = deep(t)
            if is_tuple(t):
                self.refuse(node, '%s() of a tuple (iterating a tuple is not built); name the items: %s(a, b)'
                            % (op, op))
            et = elem_of(t)
            if is_table(t):
                self.force()
                n, t = call(self.table(t).fn('keys'), n), ('list', t[1])
                et = deep(t)[1]
            if is_tuple(et):
                self.force()
                return call(self.gen.list_helper(op, et), n), et
            kws = [ast.keyword(arg=kw.arg, value=self.exv(kw.value)[0]) for kw in node.keywords]
            return self.done(node, [n], kws, et)
        if len(node.args) == 1:
            n, t = self.exv(node.args[0])
            t = deep(t)
            et = elem_of(t)
            if is_tuple(et) or has_tuple(et):
                self.refuse(node, '%s() with key= over tuples is not built; use sorted(xs, key=...)[%s] or a '
                            'loop' % (op, '-1' if op == 'max' else '0'))
            kws = self.key_kw(node, node.keywords, et)
            return self.done(node, [n], kws, et)
        args, ts, kws = self.args_ex(node)
        ts = [deep(t) for t in ts]
        if all(is_tuple(t) for t in ts):
            self.force()
            if len({code(t) for t in ts}) != 1:
                self.refuse(node, '%s() of tuples of different shapes' % op)
            fn = self.gen.pair_max(op, ts[0])
            acc = args[0]
            for a in args[1:]:
                acc = call(fn, acc, a)
            return acc, ts[0]
        t = FLT if FLT in ts else (ts[0] if ts else None)
        return self.done(node, args, kws, t)

    def b_min(self, node, want, ctx):
        return self.minmax(node, 'min')

    def b_max(self, node, want, ctx):
        return self.minmax(node, 'max')

    # ------------------------------------------------------------------------------------------
    # modules
    def call_module(self, node, mod, fn, want):
        if mod == 'heapq' and fn in HEAP_FUNCS:
            return self.heap_call(node, fn)
        if mod == 'heapq' and fn in ('nlargest', 'nsmallest') and len(node.args) == 2:
            # `heapq.nlargest(k, d.items(), key=lambda kv: kv[1])` -- the element is a tuple
            # class instance here, so the key lambda must be lowered over it like sorted()'s
            k, _ = self.exv(node.args[0])
            src, st, _ = self.iter_source(node.args[1])
            src, st = self.realize(src, st)
            st = deep(st)
            et = elem_of(st)
            if is_tuple(st):
                self.refuse(node, 'heapq.%s() of a tuple' % fn)
            kws = self.key_kw(node, node.keywords, et)
            return self.done(node, [k, src], kws, ('list', et))
        if mod == 'functools' and fn == 'reduce':
            return self.b_reduce(node, want, None)
        if mod == 'math' and fn == 'modf' and len(node.args) == 1 and not node.keywords:
            args, ts, kws = self.args_ex(node)
            t = deep(ts[0])
            if t not in NUMERIC:
                self.refuse(node, 'math.modf of a value whose type is not known to be int or float')
            self.force()
            return call(self.gen.modf(), self.coerce(args[0], t, FLT)[0]), ('tuple', (FLT, FLT))
        if mod == 'math':
            args, ts, kws = self.args_ex(node)
            if fn in MATH_FLOAT:
                return self.done(node, args, kws, FLT)
            if fn in MATH_INT:
                return self.done(node, args, kws, INT)
            return self.done(node, args, kws, None)
        if not isinstance(node.func, ast.Name):
            pass
        args, ts, kws = self.args_ex(node)
        return self.done(node, args, kws, None)

    def heap_call(self, node, fn):
        if not node.args:
            return self.generic_call(node)
        h, ht = self.exv(node.args[0])
        ht = unopt(ht)
        if not (isinstance(ht, tuple) and ht[0] == 'list'):
            args, ts, kws = self.args_ex(node)
            return self.done(node, args, kws, None)
        et = ht[1]
        args = [h]
        if fn in ('heappush', 'heappushpop', 'heapreplace') and len(node.args) > 1:
            x, xt = self.exv(node.args[1], et, 'row')
            x, xt = self.coerce(x, xt, et)
            self.fill(et, xt)
            args.append(x)
            et = ht[1]
        rest_kws = [kw for kw in node.keywords]
        node.keywords = rest_kws
        det = deep(et)
        if is_tuple(det):
            self.force()
            kws = self.key_kw(node, node.keywords, det)
        else:
            kws = [ast.keyword(arg=kw.arg, value=self.exv(kw.value)[0]) if kw.arg != 'key' or
                   not isinstance(kw.value, ast.Lambda) else
                   ast.keyword(arg='key', value=self.lambda_(kw.value, [det], 'key')[0]) for kw in node.keywords]
        ret = det if fn in ('heappop', 'heappushpop', 'heapreplace') else 'none'
        return self.done(node, args, kws, ret)

    # ------------------------------------------------------------------------------------------
    # methods
    def call_method(self, node, want):
        f = node.func
        m = f.attr
        recv, rt = self.ex(f.value)
        rt = unopt(rt)
        f.value = recv
        if is_table_dict(rt):
            return self.table_dict_method(node, recv, rt, m, want)
        if is_table_set(rt):
            return self.table_set_method(node, recv, rt, m, want)
        if isinstance(rt, tuple) and rt[0] == 'list':
            return self.list_method(node, recv, rt, m, want)
        if isinstance(rt, tuple) and rt[0] == 'dict':
            return self.dict_method(node, recv, rt, m, want)
        if isinstance(rt, tuple) and rt[0] == 'set':
            return self.set_method(node, recv, rt, m, want)
        if rt == STR:
            return self.str_method(node, recv, m)
        if isinstance(rt, tuple) and rt[0] == 'cls':
            sig = self.methods.get((rt[1], m))
            if sig is not None:
                return self.call_user(node, sig)
        if is_tuple(rt):
            if m in ('count', 'index'):
                self.refuse(node, 'tuple.%s() is not built' % m)
        args, ts, kws = self.args_ex(node)
        return self.done(node, args, kws, None)

    def str_method(self, node, recv, m):
        if m in ('partition', 'rpartition') and len(node.args) == 1:
            sep, _ = self.exv(node.args[0])
            self.force()
            return call(self.gen.partition(m == 'rpartition'), recv, sep), ('tuple', (STR, STR, STR))
        args, ts, kws = self.args_ex(node)
        if m == 'format' and any(is_tuple(t) or has_tuple(t) for t in ts):
            self.refuse(node, 'str.format with a tuple argument; use an f-string or unpack the tuple')
        self.no_tuple_items(node, ts, 'str.' + m)
        if m in STR_RET_STR:
            t = STR
        elif m in STR_RET_INT:
            t = INT
        elif m in STR_RET_BOOL:
            t = BOOL
        elif m in STR_RET_LIST:
            t = ('list', STR)
        elif m == 'encode':
            t = BYTES
        else:
            t = None
        return self.done(node, args, kws, t)

    def list_method(self, node, recv, rt, m, want):
        et = rt[1]
        det = deep(et)
        if m == 'append' and len(node.args) == 1 and not node.keywords:
            x, xt = self.exv(node.args[0], et, 'row')
            x, xt = self.coerce(x, xt, et)
            self.fill(et, xt)
            return self.done(node, [x], [], 'none')
        if m == 'extend' and len(node.args) == 1:
            x, xt = self.exv(node.args[0], rt)
            xt = deep(xt)
            if is_table(xt):
                self.force()
                x = call(self.table(xt).fn('keys'), x)
                xt = ('list', xt[1])
            if isinstance(xt, tuple) and xt[0] in ('list', 'set', 'iter'):
                self.fill(et, xt[1])
            return self.done(node, [x], [], 'none')
        if m == 'insert' and len(node.args) == 2:
            i, _ = self.exv(node.args[0], INT)
            x, xt = self.exv(node.args[1], et, 'row')
            self.fill(et, xt)
            return self.done(node, [i, x], [], 'none')
        if m == 'pop':
            args, ts, kws = self.args_ex(node, [INT])
            if is_tuple(det):
                self.force()
            return self.done(node, args, kws, et)
        if m in ('index', 'count') and is_tuple(det) and len(node.args) == 1:
            self.force()
            x, xt = self.exv(node.args[0], det)
            return call(self.gen.list_helper(m, det), recv, x), INT
        if m == 'remove' and is_tuple(det):
            self.refuse(node, 'list.remove of a tuple outside a statement; write `del xs[xs.index(t)]`')
        if m == 'sort':
            kws = self.key_kw(node, node.keywords, det)
            return self.done(node, [], kws, 'none')
        if m == 'copy':
            return self.done(node, [], [], rt)
        args, ts, kws = self.args_ex(node)
        if m in ('reverse', 'clear'):
            return self.done(node, args, kws, 'none')
        if m in ('index', 'count'):
            return self.done(node, args, kws, INT)
        return self.done(node, args, kws, None)

    def dict_method(self, node, recv, rt, m, want):
        kt, vt = rt[1], rt[2]
        if m == 'items' and not node.args:
            return node, ('items', kt, vt)
        if m == 'keys':
            return node, ('iter', kt)
        if m == 'values':
            return node, ('iter', vt)
        if m == 'setdefault' and len(node.args) == 2:
            k, ktt = self.exv(node.args[0], kt)
            v, vtt = self.exv(node.args[1], vt)
            self.fill(kt, ktt)
            self.fill(vt, vtt)
            return self.done(node, [k, v], [], vt)
        if m in ('get', 'pop') and node.args:
            k, ktt = self.exv(node.args[0], kt)
            self.fill(kt, ktt)
            rest = []
            for a in node.args[1:]:
                n_, t_ = self.exv(a, vt)
                self.fill(vt, t_)
                rest.append(n_)
            return self.done(node, [k] + rest, [], vt)
        args, ts, kws = self.args_ex(node)
        if m in ('update', 'clear'):
            return self.done(node, args, kws, 'none')
        if m == 'copy':
            return self.done(node, args, kws, rt)
        return self.done(node, args, kws, None)

    def set_method(self, node, recv, rt, m, want):
        et = rt[1]
        if m in ('add', 'discard', 'remove') and len(node.args) == 1:
            x, xt = self.exv(node.args[0], et, 'row')
            self.fill(et, xt)
            return self.done(node, [x], [], 'none')
        args, ts, kws = self.args_ex(node)
        if m in ('copy', 'union', 'intersection', 'difference', 'symmetric_difference'):
            return self.done(node, args, kws, rt)
        if m == 'pop':
            return self.done(node, args, kws, et)
        return self.done(node, args, kws, None)

    # -- tables ---------------------------------------------------------------------------------------
    def table_dict_method(self, node, recv, rt, m, want):
        self.force()
        tbl = self.table(rt)
        kt, vt = rt[1], rt[2]
        if node.keywords:
            self.refuse(node, 'keyword arguments to a dict method')
        if m in ('get', 'pop', 'setdefault', 'update'):
            if m == 'update':
                other, ot = self.exv(node.args[0], rt)
                if not is_table_dict(ot) or code(ot) != code(rt):
                    self.refuse(node, 'dict.update with something other than a dict of the same shape')
                return call(tbl.fn('update'), recv, other), 'none'
            if not node.args:
                self.refuse(node, 'dict.%s needs a key' % m)
            k, ktt = self.exv(node.args[0], kt)
            self.fill(kt, ktt)
            rest = []
            for a in node.args[1:]:
                n, t = self.exv(a, vt)
                n, t = self.coerce(n, t, vt)
                self.fill(vt, t)
                rest.append(n)
            if m == 'get':
                if len(rest) == 1:
                    return call(tbl.fn('getd'), recv, k, rest[0]), vt
                if not is_tuple(vt):
                    self.refuse(node, 'dict.get(k) without a default returns None; only a dict whose values are '
                                'tuples can do that here (give a default)')
                return call(tbl.fn('get1'), recv, k), ('opt', vt)
            if m == 'pop':
                if len(rest) == 1:
                    return call(tbl.fn('popd'), recv, k, rest[0]), vt
                return call(tbl.fn('pop'), recv, k), vt
            if len(rest) != 1:
                self.refuse(node, 'dict.setdefault needs a default')
            if tbl.rows:
                if not pure(recv):
                    self.refuse(node, 'setdefault on a dict that is not a plain name or field')
                return ast.Subscript(value=attr(fresh_copy(recv), 'vs'), slice=call(tbl.fn('sdent'), recv, k, rest[0]),
                                     ctx=ast.Load()), vt
            return call(tbl.fn('setdefault'), recv, k, rest[0]), vt
        if m == 'items':
            return call(tbl.fn('items'), recv), ('list', ('tuple', (kt, vt)))
        if m == 'keys':
            return call(tbl.fn('keys'), recv), ('list', kt)
        if m == 'values':
            return call(tbl.fn('vals'), recv), ('list', vt)
        if m == 'clear':
            return call(tbl.fn('clear'), recv), 'none'
        if m == 'copy':
            return call(tbl.fn('copy'), recv), rt
        if m == 'popitem':
            return call(tbl.fn('popitem'), recv), ('tuple', (kt, vt))
        self.refuse(node, 'dict.%s is not built for a dict with tuples' % m)

    def table_set_method(self, node, recv, rt, m, want):
        self.force()
        tbl = self.table(rt)
        et = rt[1]
        if node.keywords:
            self.refuse(node, 'keyword arguments to a set method')
        if m in ('add', 'discard', 'remove'):
            x, xt = self.exv(node.args[0], et, 'row')
            self.fill(et, xt)
            return call(tbl.fn(m), recv, x), 'none'
        if m == 'pop':
            return call(tbl.fn('spop'), recv), et
        if m == 'clear':
            return call(tbl.fn('clear'), recv), 'none'
        if m == 'copy':
            return call(tbl.fn('copy'), recv), rt
        if m in ('union', 'intersection', 'difference', 'symmetric_difference', 'issubset', 'issuperset',
                 'isdisjoint', 'update'):
            other, ot = self.exv(node.args[0], rt)
            ot = deep(ot)
            if isinstance(ot, tuple) and ot[0] == 'list':
                other = call(tbl.fn('fromlist'), other)
                ot = rt
            if not is_table_set(ot) or code(ot) != code(rt):
                self.refuse(node, 'set.%s with something other than a set / list of the same element shape' % m)
            if m == 'update':
                return call(tbl.fn('addall'), recv, call(tbl.fn('keys'), other)), 'none'
            if m == 'issuperset':
                return call(tbl.fn('subset'), other, recv), BOOL
            op = {'union': 'union', 'intersection': 'inter', 'difference': 'diff',
                  'symmetric_difference': 'symdiff', 'issubset': 'subset', 'isdisjoint': 'disjoint'}[m]
            return call(tbl.fn(op), recv, other), (BOOL if m in ('issubset', 'isdisjoint') else rt)
        self.refuse(node, 'set.%s is not built for a set of tuples' % m)
