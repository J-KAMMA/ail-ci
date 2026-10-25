"""Lambdas as values: lifted to top-level functions; captured read-only locals by monomorphising the callee.

* `f = lambda x: x * k` ... `f(3)`, `apply(f, xs)`: the name is an alias of the lambda, never an object.
* `apply(lambda x: x + k, xs)` where `apply(f: Callable[[int], int], xs)`: with nothing captured the lambda is lifted
  to `_ail_lamN` and passed by name (a plain C function pointer); with captures the callee is cloned without its
  function parameter and with the captured values as leading parameters (`apply_l1(k, xs)`), the clone calling
  `_ail_lamN(k, x)`.  A closure capture by value is CPython's late binding exactly when the captured name is not
  rebound after the lambda is made, which is checked; otherwise the lambda is refused by name.
* `map(f, xs)`, `filter(f, xs)` with a lambda or function: expanded inline to a generator expression;
  `reduce(f, xs[, init])` to a loop.
* A lambda that escapes (returned, stored in a list / dict / field) is refused by name.
"""
import ast

from tupcommon import *  # noqa: F401,F403


class LamInfo:
    def __init__(self, node, caps, line, alias=None):
        self.node, self.caps, self.line, self.alias = node, caps, line, alias   # caps: [(name, type)]
        self.lift = None


class Lift:
    def __init__(self, name_, caps, ptypes, ret):
        self.name, self.caps, self.ptypes, self.ret = name_, caps, ptypes, ret


def ann_src(t):
    """A type as a source annotation (the program's own spelling: tuples are still tuples)."""
    t = deep(t)
    if t in (INT, FLT, STR, BOOL, BYTES):
        return t
    if t == 'none':
        return 'None'
    if isinstance(t, tuple):
        k = t[0]
        if k == 'tuple':
            return 'tuple[%s]' % ', '.join(ann_src(e) for e in t[1])
        if k == 'list':
            return 'list[%s]' % ann_src(t[1])
        if k == 'set':
            return 'set[%s]' % ann_src(t[1])
        if k == 'dict':
            return 'dict[%s, %s]' % (ann_src(t[1]), ann_src(t[2]))
        if k == 'cls':
            return t[1]
        if k == 'opt':
            return 'Optional[%s]' % ann_src(t[1])
    raise Refused((1, 'cannot spell the type of a lambda parameter, capture or result; annotate the function that '
                   'takes it'))


class Names(ast.NodeVisitor):
    """Free names of a lambda: loaded and not bound inside it."""
    def __init__(self, params):
        self.loads, self.bound = [], set(params)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.loads.append(node.id)
        else:
            self.bound.add(node.id)

    def visit_Lambda(self, node):
        for a in node.args.args:
            self.bound.add(a.arg)
        self.generic_visit(node)


class Subst(ast.NodeTransformer):
    def __init__(self, mapping):
        self.mapping = mapping

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.mapping:
            return fresh_copy(self.mapping[node.id])
        return node


class Lams:
    # ------------------------------------------------------------------------------------------
    def nested_scope_reads(self, fn):
        """Names loaded inside a nested def or lambda of `fn`.  A lambda assigned to one of them
        is left as written: the alias lowering below removes the assignment, but it does not enter
        nested scopes, so their call would otherwise read a module-level name of the same spelling."""
        out = set()

        def walk(node):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    out.update(n.id for n in ast.walk(child)
                               if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load))
                else:
                    walk(child)
        walk(fn)
        return out

    def scan_binds(self, fn):
        """name -> [(line, loops)] of every place a function binds it (parameters: line 0)."""
        binds = {}

        def add(nm, line, loops):
            binds.setdefault(nm, []).append((line, loops))

        for a in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]:
            add(a.arg, 0, ())
        if fn.args.vararg:
            add(fn.args.vararg.arg, 0, ())
        if fn.args.kwarg:
            add(fn.args.kwarg.arg, 0, ())

        def targets(node, line, loops):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                    add(sub.id, line, loops)

        def walk(body, loops):
            for st in body:
                line = getattr(st, "lineno", 0)
                if isinstance(st, (ast.For, ast.AsyncFor)):
                    inner = loops + (id(st),)
                    targets(st.target, line, inner)
                    walk(st.body, inner)
                    walk(st.orelse, loops)
                    continue
                if isinstance(st, ast.While):
                    inner = loops + (id(st),)
                    walk(st.body, inner)
                    walk(st.orelse, loops)
                    continue
                if isinstance(st, ast.Assign):
                    for t in st.targets:
                        targets(t, line, loops)
                elif isinstance(st, (ast.AugAssign, ast.AnnAssign)):
                    targets(st.target, line, loops)
                elif isinstance(st, ast.Delete):
                    for t in st.targets:
                        targets(t, line, loops)
                elif isinstance(st, ast.With):
                    for item in st.items:
                        if item.optional_vars is not None:
                            targets(item.optional_vars, line, loops)
                elif isinstance(st, ast.Try):
                    for h in st.handlers:
                        if h.name:
                            add(h.name, h.lineno, loops)
                elif isinstance(st, (ast.Import, ast.ImportFrom)):
                    for a in st.names:
                        add((a.asname or a.name).split('.')[0], line, loops)
                for field in ('body', 'orelse', 'finalbody'):
                    sub = getattr(st, field, None)
                    if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                        walk(sub, loops)
                if isinstance(st, ast.Try):
                    for h in st.handlers:
                        walk(h.body, loops)
                if isinstance(st, ast.Match):
                    for case in st.cases:
                        walk(case.body, loops)
                for sub in ast.walk(st):
                    if isinstance(sub, ast.NamedExpr):
                        add(sub.target.id, line, loops)

        walk(fn.body, ())
        self.binds = binds

    def captures(self, lam, line):
        """[(name, type)] captured by value, after checking CPython's late binding cannot differ."""
        params = {a.arg for a in lam.args.args}
        v = Names(params)
        v.visit(lam.body)
        out, seen = [], set()
        for nm in v.loads:
            if nm in v.bound or nm in seen:
                continue
            seen.add(nm)
            if nm in self.lam_alias:
                self.refuse(lam, 'a lambda that calls the lambda %s; write the body out' % nm)
            if nm in self.alias:
                self.refuse(lam, 'a lambda capturing the comprehension variable %s' % nm)
            if nm not in self.binds:
                continue                      # a global function, constant, class or builtin
            for site, _ in self.binds[nm]:
                if site >= line:
                    self.refuse(lam, 'the lambda captures %s, which is assigned again after the lambda is made '
                                '(CPython reads it when the lambda is called); pass it as a parameter instead' % nm)
            t = self.env.get(nm)
            if t is None or not known(t):
                self.refuse(lam, 'cannot tell the type of %s, captured by this lambda; annotate it' % nm)
            out.append((nm, deep(t)))
        return out

    def make_lift(self, info, ptypes):
        """Lift the lambda of `info` to a top-level function taking its captures, then its parameters."""
        lam = info.node
        if info.lift is not None:
            if [code(a) for a in info.lift.ptypes] != [code(b) for b in ptypes]:
                self.refuse(lam, 'one lambda used with arguments of different types')
            return info.lift
        if lam.args.defaults or lam.args.vararg or lam.args.kwarg or lam.args.kwonlyargs:
            self.refuse(lam, 'a lambda with default, *args or keyword-only parameters')
        if len(lam.args.args) != len(ptypes):
            self.refuse(lam, 'a lambda called with %d arguments but taking %d' % (len(ptypes), len(lam.args.args)))
        for t in ptypes:
            if not known(t):
                self.refuse(lam, 'cannot tell the type of an argument of this lambda; annotate the function that '
                            'takes it')
        saved = self.env
        self.env = dict(saved)
        for (nm, t) in info.caps:
            self.env[nm] = t
        for a, t in zip(lam.args.args, ptypes):
            self.env[a.arg] = t
        try:
            ret = self.typeof(lam.body)
        finally:
            self.env = saved
        if ret is None or not known(ret) or ret == 'none':
            self.refuse(lam, 'cannot tell the result type of this lambda')
        self.lam_counter += 1
        nm = '_ail_lam%d' % self.lam_counter
        while nm in self.names:
            self.lam_counter += 1
            nm = '_ail_lam%d' % self.lam_counter
        self.names.add(nm)
        params = [(c, t) for c, t in info.caps] + [(a.arg, t) for a, t in zip(lam.args.args, ptypes)]
        src = 'def %s(%s) -> %s:\n    return 0\n' % (
            nm, ', '.join('%s: %s' % (p, ann_src(t)) for p, t in params), ann_src(ret))
        fn = ast.parse(src).body[0]
        fn.body = [ast.Return(value=fresh_copy(lam.body))]
        ast.fix_missing_locations(fn)
        sig = Sig(fn, None)
        sig.params = [(p, t, False) for p, t in params]
        sig.ret = ret
        self.sigs[id(fn)] = sig
        self.funcs[nm] = sig
        self.lamdefs.append(fn)
        info.lift = Lift(nm, info.caps, list(ptypes), ret)
        self.force()
        return info.lift

    def lam_info(self, node):
        """LamInfo of a lambda literal or an alias name (None for anything else)."""
        if isinstance(node, ast.Lambda):
            return LamInfo(fresh_copy(node), self.captures(node, node.lineno), node.lineno)
        if isinstance(node, ast.Name) and node.id in self.lam_alias:
            info = self.lam_alias[node.id]
            if node.lineno <= info.line and info.line:
                self.refuse(node, 'the lambda %s is used before it is made' % node.id)
            return info
        return None

    def call_args(self, lift, args):
        return [name(c) for c, _ in lift.caps] + list(args)

    # -- aliases ----------------------------------------------------------------------------------------
    def lam_assign(self, st):
        tgt = st.targets[0]
        nm = tgt.id
        if len(self.binds.get(nm, [])) != 1:
            self.refuse(st, 'a lambda assigned to a name %s that is assigned more than once' % nm)
        info = LamInfo(fresh_copy(st.value), self.captures(st.value, st.lineno), st.lineno, nm)
        self.lam_alias[nm] = info
        self.force()
        return []

    def call_alias(self, node, info):
        """f(args) with f an alias of a lambda."""
        args, ts, kws = self.args_ex(node)
        if kws:
            self.refuse(node, 'keyword arguments to a lambda')
        lift = self.make_lift(info, [deep(t) for t in ts])
        return call(lift.name, *self.call_args(lift, args)), lift.ret

    # -- passing a lambda to a function taking Callable ------------------------------------------------------
    def lam_arg(self, sig, pidx, arg_node, callee_node):
        """(new argument node, extra leading args, clone name) for a lambda passed as parameter pidx."""
        pt = deep(sig.params[pidx][1])
        if not (isinstance(pt, tuple) and pt[0] == 'callable'):
            return None
        info = self.lam_info(arg_node)
        if info is None:
            return None
        lift = self.make_lift(info, [deep(p) for p in pt[1]])
        if deep(pt[2]) is not None and code(pt[2]) != code(lift.ret) and not (deep(pt[2]) == FLT and lift.ret == INT):
            self.refuse(arg_node, 'the lambda returns %s but the parameter says %s' % (lift.ret, deep(pt[2])))
        if not lift.caps:
            return name(lift.name), None, None
        clone = self.specialize(sig, pidx, lift)
        return None, [name(c) for c, _ in lift.caps], clone

    def specialize(self, sig, pidx, lift):
        key = (sig.node.name, pidx, lift.name)
        if key in self.specs:
            return self.specs[key]
        if sig.owner:
            self.refuse(sig.node, 'a lambda with captures passed to a method (%s)' % sig.node.name)
        orig = self.pristine.get(sig.node.name)
        if orig is None:
            self.refuse(sig.node, 'cannot specialise %s' % sig.node.name)
        fn = fresh_copy(orig)
        pname = fn.args.args[pidx].arg
        ndefault = len(fn.args.defaults)
        if pidx >= len(fn.args.args) - ndefault:
            self.refuse(fn, 'the function parameter %s of %s has a default' % (pname, fn.name))
        clone_name = '%s_l%d' % (fn.name, len(self.specs) + 1)
        while clone_name in self.names:
            clone_name += '_'
        self.names.add(clone_name)
        self.specs[key] = clone_name
        capnames = [('_cap%d_%s' % (i, c), t) for i, (c, t) in enumerate(lift.caps)]
        del fn.args.args[pidx]
        fn.args.args[0:0] = [ast.arg(arg=n_, annotation=ast.parse(ann_src(t), mode='eval').body)
                             for n_, t in capnames]
        fn.name = clone_name
        mapping = dict(zip([c for c, _ in lift.caps], [n_ for n_, _ in capnames]))
        outer = self

        class Rewrite(ast.NodeTransformer):
            def visit_Call(self, node):
                f = node.func
                if isinstance(f, ast.Name) and f.id == pname:
                    args = [self.visit(a) for a in node.args]
                    kws = [self.visit(k) for k in node.keywords]
                    return ast.Call(func=name(lift.name), args=[name(n_) for n_, _ in capnames] + args,
                                    keywords=kws)
                if isinstance(f, ast.Name) and f.id in outer.funcs and f.id in outer.pristine:
                    callee = outer.funcs[f.id]
                    for j, a in enumerate(node.args):
                        if isinstance(a, ast.Name) and a.id == pname:
                            pt = deep(callee.params[j][1]) if j < len(callee.params) else None
                            if isinstance(pt, tuple) and pt[0] == "callable":
                                if not lift.caps:
                                    node.args[j] = name(lift.name)
                                    break
                                sub_ = outer.specialize(callee, j, lift)
                                args = [self.visit(x) for k, x in enumerate(node.args) if k != j]
                                kws = [self.visit(k) for k in node.keywords]
                                return ast.Call(func=name(sub_), args=[name(n_) for n_, _ in capnames] + args,
                                                keywords=kws)
                self.generic_visit(node)
                return node

            def visit_Name(self, node):
                if node.id == pname:
                    if not lift.caps:
                        return name(lift.name)
                    outer.refuse(fn, 'the function parameter %s of %s is used as a value (stored, returned or '
                                 'passed on), which a lambda with captures cannot be' % (pname, orig.name))
                return node

        fn = Rewrite().visit(fn)
        ast.fix_missing_locations(fn)
        sig2 = self.make_sig(fn, None)
        sig2.params = [(a.arg, self.ann(a.annotation), False) for a in fn.args.args]
        self.funcs[clone_name] = sig2
        self.pristine[clone_name] = fresh_copy(fn)
        self.lamdefs.append(fn)
        self.force()
        return clone_name

    # -- map / filter / reduce -------------------------------------------------------------------------------
    def fn_call_node(self, f, args, node):
        """An expression calling f (lambda, alias, function or builtin name) on the given argument nodes."""
        if isinstance(f, ast.Lambda):
            if len(f.args.args) != len(args) or f.args.defaults or f.args.vararg or f.args.kwonlyargs:
                self.refuse(node, 'a lambda with a different number of parameters than arguments')
            return Subst(dict(zip([a.arg for a in f.args.args], args))).visit(fresh_copy(f.body))
        if isinstance(f, ast.Name) and f.id in self.lam_alias:
            return self.fn_call_node(self.lam_alias[f.id].node, args, node)
        if isinstance(f, ast.Name):
            return ast.Call(func=name(f.id), args=list(args), keywords=[])
        self.refuse(node, 'the function argument of map / filter / reduce is not a lambda or a function name')

    def lam_involved(self, f):
        return isinstance(f, ast.Lambda) or (isinstance(f, ast.Name) and f.id in self.lam_alias)

    def b_map(self, node, want, ctx):
        if not (node.args and self.lam_involved(node.args[0])):
            return self.generic_call(node)
        if len(node.args) < 2 or node.keywords:
            self.refuse(node, 'map with several iterables or keywords')
        if len(node.args) > 2:
            self.refuse(node, 'map over several iterables; use a comprehension with zip')
        var = self.fresh('mv')
        elt = self.fn_call_node(node.args[0], [name(var)], node)
        gen = ast.GeneratorExp(elt=elt, generators=[ast.comprehension(
            target=ast.Name(id=var, ctx=ast.Store()), iter=node.args[1], ifs=[], is_async=0)])
        if self.lam_involved(node.args[0]):
            self.force()
        return self.ex(gen, want, ctx)

    def b_filter(self, node, want, ctx):
        if not (node.args and self.lam_involved(node.args[0])):
            return self.generic_call(node)
        if len(node.args) != 2 or node.keywords:
            self.refuse(node, 'filter takes a function and one iterable')
        var = self.fresh('mv')
        if isinstance(node.args[0], ast.Constant) and node.args[0].value is None:
            cond = name(var)
        else:
            cond = self.fn_call_node(node.args[0], [name(var)], node)
        gen = ast.GeneratorExp(elt=name(var), generators=[ast.comprehension(
            target=ast.Name(id=var, ctx=ast.Store()), iter=node.args[1], ifs=[cond], is_async=0)])
        if self.lam_involved(node.args[0]):
            self.force()
        return self.ex(gen, want, ctx)

    def b_reduce(self, node, want, ctx):
        if len(node.args) not in (2, 3) or node.keywords:
            self.refuse(node, 'reduce takes a function, an iterable and an optional initial value')
        if self.nohoist:
            self.refuse(node, 'reduce inside a condition, a lambda or a comprehension; use a loop')
        acc, x = self.fresh('ra'), self.fresh('rx')
        src, st = self.exv(node.args[1])
        et = elem_of(st)
        if len(node.args) == 3:
            init, it = self.exv(node.args[2])
            pre = [ast.Assign(targets=[ast.Name(id=acc, ctx=ast.Store())], value=init, lineno=0)]
            loop_iter = src
        else:
            if not (isinstance(deep(st), tuple) and deep(st)[0] == 'list'):
                self.refuse(node, 'reduce without an initial value over something that is not a list')
            if not pure(src):
                tmp = self.fresh()
                self.pre.append(ast.Assign(targets=[ast.Name(id=tmp, ctx=ast.Store())], value=src, lineno=0))
                self.env[tmp] = st
                src = name(tmp)
            it = et
            pre = [ast.Assign(targets=[ast.Name(id=acc, ctx=ast.Store())],
                              value=ast.Subscript(value=fresh_copy(src), slice=const(0), ctx=ast.Load()), lineno=0)]
            loop_iter = ast.Subscript(value=fresh_copy(src), slice=ast.Slice(lower=const(1), upper=None, step=None),
                                      ctx=ast.Load())
        self.env[acc] = it
        self.env[x] = et
        body_expr = self.fn_call_node(node.args[0], [name(acc), name(x)], node)
        loop = ast.For(target=ast.Name(id=x, ctx=ast.Store()), iter=loop_iter,
                       body=[ast.Assign(targets=[ast.Name(id=acc, ctx=ast.Store())], value=body_expr, lineno=0)],
                       orelse=[])
        # lower the loop like any statement (types, tuple unpacking inside the body)
        lowered = self.stmts([*pre, loop])
        self.pre.extend(lowered)
        self.force()
        return name(acc), it
