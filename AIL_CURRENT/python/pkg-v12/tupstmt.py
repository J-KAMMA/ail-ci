"""Statement lowering of the tuple pass."""
import ast

from tupcommon import *  # noqa: F401,F403
from tupexpr import unopt


EMPTY_CALLS = ('list', 'dict', 'set')


def is_empty_display(node):
    if isinstance(node, ast.ListComp) and len(node.generators) == 1:
        return is_empty_display(node.elt)
    if isinstance(node, ast.List):
        return not node.elts
    if isinstance(node, ast.Dict):
        return not node.keys
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in EMPTY_CALLS \
            and not node.args and not node.keywords:
        return True
    return False


def store(node):
    node = fresh_copy(node)
    for sub in ast.walk(node):
        if hasattr(sub, 'ctx'):
            sub.ctx = ast.Store() if sub is node else sub.ctx
    return node


class Stmts:
    # ------------------------------------------------------------------------------------------
    def stmts(self, body):
        out = []
        for st in body:
            saved = self.pre
            self.pre = []
            try:
                new = self.stmt(st)
                out.extend(self.pre)
                out.extend(new)
            except Refused as exc:
                self.errors.append(exc.args[0])
                out.append(st)
            self.pre = saved
        return out

    def stmt(self, st):
        method = getattr(self, 'stmt_' + type(st).__name__, None)
        if method is None:
            return self.stmt_generic(st)
        return method(st)

    def stmt_generic(self, st):
        for field, value in ast.iter_fields(st):
            if isinstance(value, ast.expr):
                setattr(st, field, self.exv(value)[0])
            elif isinstance(value, list):
                setattr(st, field, [self.exv(v)[0] if isinstance(v, ast.expr) else v for v in value])
        return [st]

    def typeof(self, node):
        """The type of an expression, without lowering it in place or forcing the program."""
        forced, errors = self.forced, len(self.errors)
        saved_quiet, saved_pre = self.quiet, self.pre
        self.quiet += 1
        self.pre = []
        try:
            return deep(self.ex(fresh_copy(node))[1])
        except Refused:
            return None
        finally:
            self.quiet = saved_quiet
            self.pre = saved_pre
            self.forced = forced
            del self.errors[errors:]

    def stmt_FunctionDef(self, st):
        return [st]

    stmt_AsyncFunctionDef = stmt_FunctionDef
    stmt_ClassDef = stmt_FunctionDef

    def stmt_Pass(self, st):
        return [st]

    stmt_Break = stmt_Continue = stmt_Global = stmt_Nonlocal = stmt_Import = stmt_ImportFrom = stmt_Pass

    def stmt_Return(self, st):
        if st.value is None:
            return [st]
        want = self.cur.ret if self.cur is not None else None
        v, t = self.exv(st.value, want)
        v, t = self.coerce(v, t, want)
        st.value = v
        self.rets.append(deep(t))
        if is_tuple(t):
            self.force()
        return [st]

    def stmt_Expr(self, st):
        v = st.value
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute):
            m = v.func.attr
            if m == 'sort' and not v.args:
                out = self.sort_statement(st)
                if out is not None:
                    return out
            if m == 'remove' and len(v.args) == 1:
                out = self.remove_statement(st)
                if out is not None:
                    return out
        if isinstance(v, ast.Constant):
            return [st]
        st.value, _ = self.exv(v)
        return [st]

    def sort_statement(self, st):
        """list.sort() of tuples with more than 4 scalar fields: successive stable sorts (last field first)."""
        v = st.value
        recv, rt = self.ex(fresh_copy(v.func.value))
        rt = unopt(rt)
        if not (isinstance(rt, tuple) and rt[0] == 'list' and is_tuple(rt[1])):
            return None
        if any(kw.arg == 'key' for kw in v.keywords):
            return None
        lv = leaves(rt[1], '_k')
        if len(lv) <= 4:
            return None
        self.force()
        recv, _ = self.exv(v.func.value)
        reverse = [kw for kw in v.keywords if kw.arg == 'reverse']
        groups = [lv[i:i + 4] for i in range(0, len(lv), 4)]
        out = []
        for g in reversed(groups):
            body = ('(%s)' % ', '.join(p if t != BOOL else 'int(%s)' % p for p, t in g)) if len(g) > 1 else (
                g[0][0] if g[0][1] != BOOL else 'int(%s)' % g[0][0])
            lam = ast.parse('lambda _k: ' + body, mode='eval').body
            kws = [ast.keyword(arg='key', value=lam)] + [ast.keyword(arg='reverse', value=r.value) for r in reverse]
            out.append(ast.Expr(value=call(attr(fresh_copy(recv), 'sort'), keywords=kws)))
        return out

    def remove_statement(self, st):
        v = st.value
        recv, rt = self.ex(fresh_copy(v.func.value))
        rt = unopt(rt)
        if not (isinstance(rt, tuple) and rt[0] == 'list' and is_tuple(rt[1])):
            return None
        self.force()
        recv, _ = self.exv(v.func.value)
        x, _ = self.exv(v.args[0], rt[1])
        if not pure(recv):
            self.refuse(st, 'list.remove of a tuple on a list that is not a plain name or field')
        idx = call(self.gen.list_helper('index', rt[1]), recv, x)
        return [ast.Delete(targets=[ast.Subscript(value=fresh_copy(recv), slice=idx, ctx=ast.Del())])]

    # ------------------------------------------------------------------------------------------
    def stmt_If(self, st):
        st.test = self.test(st.test)
        st.body = self.stmts(st.body)
        st.orelse = self.stmts(st.orelse)
        return [st]

    def stmt_While(self, st):
        self.nohoist += 1
        try:
            st.test = self.test(st.test)
        finally:
            self.nohoist -= 1
        st.body = self.stmts(st.body)
        st.orelse = self.stmts(st.orelse)
        return [st]

    def stmt_For(self, st):
        h = self.header(st.target, st.iter, False)
        # a table walked through a snapshot must not be changed by its own loop (CPython raises)
        src = st.iter
        while isinstance(src, ast.Call) and isinstance(src.func, ast.Attribute) and src.func.attr in (
                'items', 'keys', 'values'):
            src = src.func.value
        if isinstance(src, ast.Name) and is_table(self.env.get(src.id)) and stores(st.body, src.id):
            self.refuse(st, 'a loop that changes the dict / set of tuples it walks (CPython raises RuntimeError)')
        body = []
        for cond in h.ifs:
            body.append(ast.If(test=ast.UnaryOp(op=ast.Not(), operand=cond), body=[ast.Continue()], orelse=[]))
        for target, access, t in h.unpacks:
            body.extend(self.assign_one(target, access, t, st))
        body.extend(self.stmts(st.body))
        new = ast.For(target=h.target, iter=h.iter, body=body, orelse=self.stmts(st.orelse))
        return [*h.pre, new]

    def stmt_With(self, st):
        for item in st.items:
            item.context_expr = self.exv(item.context_expr)[0]
        st.body = self.stmts(st.body)
        return [st]

    def stmt_Try(self, st):
        st.body = self.stmts(st.body)
        for h in st.handlers:
            h.body = self.stmts(h.body)
        st.orelse = self.stmts(st.orelse)
        st.finalbody = self.stmts(st.finalbody)
        return [st]

    stmt_TryStar = stmt_Try

    def stmt_Raise(self, st):
        if st.exc is not None:
            st.exc = self.exv(st.exc)[0]
        return [st]

    def stmt_Assert(self, st):
        st.test = self.test(st.test)
        if st.msg is not None:
            st.msg = self.exv(st.msg)[0]
        return [st]

    def stmt_Delete(self, st):
        out = []
        for tgt in st.targets:
            if isinstance(tgt, ast.Subscript):
                c, ct = self.exv(tgt.value)
                ct = deep(ct)
                if is_table_dict(ct):
                    self.force()
                    k, _ = self.exv(tgt.slice, ct[1])
                    out.append(ast.Expr(value=call(self.table(ct).fn('del'), c, k)))
                    continue
                tgt.value = c
                tgt.slice = self.exv(tgt.slice)[0]
            out.append(ast.Delete(targets=[tgt]))
        return out

    # ------------------------------------------------------------------------------------------
    # assignment
    def tgt_type(self, tgt):
        if isinstance(tgt, ast.Name):
            return self.env.get(tgt.id)
        if isinstance(tgt, (ast.Subscript, ast.Attribute)):
            return self.typeof(tgt)
        return None

    def bind_name(self, tgt, t):
        if tgt.id == '_':
            return
        cur = self.env.get(tgt.id)
        old, new = R(cur), R(t)
        if isinstance(old, tuple) and isinstance(new, tuple) and old[0] != new[0] \
                and old[0] in ('dict', 'set', 'list', 'tuple') and new[0] in ('dict', 'set', 'list', 'tuple'):
            # one type per name: a name rebound to another container type would keep the first type for its methods
            self.refuse(tgt, 'the name %r is bound to a %s and to a %s' % (tgt.id, old[0], new[0]))
        if cur is None or R(cur) is None:
            self.env[tgt.id] = t

    def assign_one(self, tgt, value, vt, st):
        """`tgt = value` (value already lowered, of type vt) as statements."""
        raw = vt
        vt = deep(vt)
        if isinstance(tgt, ast.Name):
            self.bind_name(tgt, raw)
            if is_tuple(vt):
                self.force()
            return [ast.Assign(targets=[tgt], value=value, lineno=getattr(st, 'lineno', 0))]
        if isinstance(tgt, ast.Subscript):
            c, ct = self.exv(tgt.value)
            ct = R(ct)
            if is_table_dict(ct):
                self.force()
                k, kt = self.exv(tgt.slice, ct[1])
                self.fill(ct[1], kt)
                self.fill(ct[2], vt)
                value, _ = self.coerce(value, vt, ct[2])
                return [ast.Expr(value=call(self.table(ct).fn('set'), c, k, value))]
            k, kt = self.exv(tgt.slice, ct[1] if isinstance(ct, tuple) and ct[0] == 'dict' else None)
            if isinstance(ct, tuple) and ct[0] == 'dict':
                self.fill(ct[1], kt)
                self.fill(ct[2], vt)
            elif isinstance(ct, tuple) and ct[0] == 'list':
                self.fill(ct[1], vt)
            tgt.value, tgt.slice = c, k
            return [ast.Assign(targets=[tgt], value=value, lineno=getattr(st, 'lineno', 0))]
        if isinstance(tgt, ast.Attribute):
            tgt.value = self.exv(tgt.value)[0]
            return [ast.Assign(targets=[tgt], value=value, lineno=getattr(st, 'lineno', 0))]
        if isinstance(tgt, ast.Starred):
            self.refuse(st, 'a starred assignment target')
        self.refuse(st, 'this assignment target is not built')

    def stmt_Assign(self, st):
        tgts = st.targets
        key = (self.fnkey, getattr(st, "lineno", 0), getattr(st, "col_offset", 0))
        if len(tgts) == 1 and isinstance(tgts[0], ast.Name) and isinstance(st.value, ast.Lambda):
            return self.lam_assign(st)
        # a, b = x, y  (parallel assignment with a literal tuple on the right)
        if len(tgts) == 1 and isinstance(tgts[0], (ast.Tuple, ast.List)) and isinstance(st.value, ast.Tuple) \
                and len(tgts[0].elts) == len(st.value.elts) \
                and not any(isinstance(e, (ast.Starred, ast.Tuple, ast.List)) for e in tgts[0].elts + st.value.elts):
            vals = [self.exv(e) for e in st.value.elts]
            simple = all(isinstance(t, ast.Name) or (isinstance(t, ast.Attribute)) or
                         (isinstance(t, ast.Subscript) and not is_table(self.typeof(t.value)))
                         for t in tgts[0].elts)
            for t, (v, vt) in zip(tgts[0].elts, vals):
                if isinstance(t, ast.Name):
                    self.bind_name(t, vt)
                    if is_tuple(vt):
                        self.force()
            if simple:
                tgts[0].elts = [self.target_parts(t) for t in tgts[0].elts]
                st.value = ast.Tuple(elts=[v for v, _ in vals], ctx=ast.Load())
                return [st]
            out, temps = [], []
            for (v, vt) in vals:
                tmp = self.fresh()
                self.env[tmp] = vt
                out.append(ast.Assign(targets=[ast.Name(id=tmp, ctx=ast.Store())], value=v, lineno=getattr(st, "lineno", 0)))
                temps.append((tmp, vt))
            for t, (tmp, vt) in zip(tgts[0].elts, temps):
                out.extend(self.assign_one(t, name(tmp), vt, st))
            return out
        # one value, one or several targets
        first = tgts[0]
        want = None
        if isinstance(first, ast.Name):
            want = self.env.get(first.id)
            if want is None and is_empty_display(st.value):
                want = self.hints.get(key)
        elif isinstance(first, (ast.Subscript, ast.Attribute)):
            want = self.tgt_type(first)
        v, vt = self.exv(st.value, want)
        if want is not None and not isinstance(first, ast.Name):
            v, vt = self.coerce(v, vt, want)
        rawvt = vt
        vt = deep(vt)
        out = []
        for tgt in tgts:
            if isinstance(tgt, (ast.Tuple, ast.List)):
                out.extend(self.unpack(tgt, v, vt, st))
            elif isinstance(tgt, ast.Name) and (is_empty_display(st.value) or (
                    isinstance(st.value, ast.List) and has_tuple(vt) and known(vt))):
                self.bind_name(tgt, rawvt)
                self.pending.append((key, self.env.get(tgt.id)))
                if known(vt) and isinstance(vt, tuple) and vt[0] in ("list", "dict", "set"):
                    self.use_type(vt)
                    elems = v.elts if isinstance(v, ast.List) and v.elts else []
                    if elems:                      # the compiler builds a non-empty list of classes only by append
                        v = ast.List(elts=[], ctx=ast.Load())
                    out.append(ast.AnnAssign(target=tgt, annotation=ast.parse(ann_text(vt), mode='eval').body,
                                             value=v, simple=1, lineno=getattr(st, "lineno", 0)))
                    for e in elems:
                        out.append(ast.Expr(value=call(attr(fresh_copy(tgt), 'append'), e)))
                    if is_tuple(vt) or is_table(vt):
                        self.force()
                else:
                    out.append(ast.Assign(targets=[tgt], value=v, lineno=getattr(st, "lineno", 0)))
            else:
                out.extend(self.assign_one(tgt, v if len(tgts) == 1 else fresh_copy(v), rawvt, st))
        return out

    def target_parts(self, t):
        if isinstance(t, ast.Attribute):
            t.value = self.exv(t.value)[0]
        elif isinstance(t, ast.Subscript):
            t.value = self.exv(t.value)[0]
            t.slice = self.exv(t.slice)[0]
        return t

    def unpack(self, tgt, v, vt, st):
        """`a, b = v` for a tuple-typed v."""
        vt = deep(vt)
        if isinstance(vt, tuple) and vt[0] == 'opt' and is_tuple(deep(vt[1])):
            vt = deep(vt[1])           # a tuple | None that the program has tested: CPython raises TypeError on None
        if not is_tuple(vt):
            if vt is None:
                self.bind_pattern(tgt, None)
                return [ast.Assign(targets=[tgt], value=v, lineno=getattr(st, "lineno", 0))]
            if isinstance(vt, tuple) and vt[0] == 'list' and not has_tuple(vt):
                self.bind_pattern(tgt, None)
                return [ast.Assign(targets=[tgt], value=v, lineno=getattr(st, "lineno", 0))]
            self.refuse(st, 'unpacking a value that is not a tuple of known shape')
        self.force()
        targets_names = {n.id for n in ast.walk(tgt) if isinstance(n, ast.Name)}
        used = {n.id for n in ast.walk(v) if isinstance(n, ast.Name)}
        out = []
        if pure(v) and not (targets_names & used):
            src = v
        else:
            tmp = self.fresh()
            self.env[tmp] = vt
            out.append(ast.Assign(targets=[ast.Name(id=tmp, ctx=ast.Store())], value=v, lineno=getattr(st, "lineno", 0)))
            src = name(tmp)
        for target, access, t in self.plan(tgt, src, vt):
            out.extend(self.assign_one(target, access, t, st))
        return out

    def stmt_AnnAssign(self, st):
        ann, t = self.map_ann(st.annotation)
        t = deep(t) if t is not None else None
        st.annotation = ann
        if isinstance(st.target, ast.Name) and t is not None:
            self.env.setdefault(st.target.id, t)
        if t is not None and (is_tuple(t) or is_table(t)):
            self.force()
        if st.value is not None:
            v, vt = self.exv(st.value, t)
            v, vt = self.coerce(v, vt, t)
            st.value = v
            if isinstance(st.target, ast.Name) and t is None:
                self.bind_name(st.target, vt)
        if not isinstance(st.target, ast.Name):
            st.target = self.target_parts(st.target)
        return [st]

    def stmt_AugAssign(self, st):
        tgt = st.target
        if isinstance(tgt, ast.Subscript):
            c, ct = self.exv(tgt.value)
            ct = deep(ct)
            if is_table_dict(ct):
                self.force()
                if not pure(c):
                    self.refuse(st, 'an augmented assignment on a dict that is not a plain name or field')
                k, _ = self.exv(tgt.slice, ct[1])
                v, vt = self.exv(st.value, ct[2])
                v, vt = self.coerce(v, vt, ct[2])
                ent = call(self.table(ct).fn('ent'), c, k)
                tgt2 = ast.Subscript(value=attr(fresh_copy(c), 'vs'), slice=ent, ctx=ast.Store())
                return [ast.AugAssign(target=tgt2, op=st.op, value=v)]
            tgt.value = c
            tgt.slice = self.exv(tgt.slice, ct[1] if isinstance(ct, tuple) and ct[0] == 'dict' else None)[0]
        elif isinstance(tgt, ast.Attribute):
            tgt.value = self.exv(tgt.value)[0]
        else:
            tt = self.env.get(tgt.id) if isinstance(tgt, ast.Name) else None
            if is_table_set(tt):
                return self.set_augassign(st, tt)
            if is_tuple(tt):
                self.refuse(st, 'an augmented assignment on a tuple (tuples are immutable; build the new one)')
        w = self.tgt_type(tgt) if isinstance(tgt, ast.Name) else None
        v, vt = self.exv(st.value, w)
        st.value = v
        return [st]

    def set_augassign(self, st, tt):
        self.force()
        tgt = st.target
        if not pure(tgt):
            self.refuse(st, 'an augmented set operation on something that is not a plain name or field')
        o, ot = self.exv(st.value, tt)
        ot = deep(ot)
        if not is_table_set(ot) or code(ot) != code(tt):
            self.refuse(st, 'a set operation with a set of another shape')
        tbl = self.table(tt)
        if isinstance(st.op, ast.BitOr):
            return [ast.Expr(value=call(tbl.fn('addall'), fresh_copy(tgt), call(tbl.fn('keys'), o)))]
        fn = {ast.BitAnd: 'inter', ast.Sub: 'diff', ast.BitXor: 'symdiff'}.get(type(st.op))
        if fn is None:
            self.refuse(st, 'this set operator')
        tmp = self.fresh()
        self.env[tmp] = tt
        return [ast.Assign(targets=[ast.Name(id=tmp, ctx=ast.Store())], value=call(tbl.fn(fn), fresh_copy(tgt), o),
                           lineno=getattr(st, "lineno", 0)),
                ast.Expr(value=call(tbl.fn('clear'), fresh_copy(tgt))),
                ast.Expr(value=call(tbl.fn('addall'), fresh_copy(tgt), call(tbl.fn('keys'), name(tmp))))]
