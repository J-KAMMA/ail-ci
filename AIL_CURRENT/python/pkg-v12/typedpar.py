# -*- coding: utf-8 -*-
"""typedpar.py -- typed parallelism without a lock (docs/design/TYPED_PARALLEL.md).

Owner decision 2026-10-19: code on the typed path drops the GIL and is kept free of data races at compile
time, with Python's own APIs, so the same program runs on CPython. This source pass runs in
ail_syntax.python_surface BEFORE threadlib.py (the G12 GIL threads of the general path). It lowers two
fork-join shapes onto `parallel for` (parallel.py checks the body, cruntime.PAR runs it on threads):

  * `ThreadPoolExecutor(max_workers=k).map(f, xs[, ys])` and `multiprocessing.Pool(k).map(f, xs)` where
    `f` is a module-level function over int / float that does nothing else (parallel.check_callee):
    the call becomes `_ail_pmap<n>(xs, k)`, a generated function whose loop is
    `for i in _ail_par_range(0, len(xs), k): r[i] = f(xs[i])`. Results come back in order, as list().
  * `ts = [threading.Thread(target=w, args=(k, out, ...)) for k in range(T)]`, `for t in ts: t.start()`,
    `for t in ts: t.join()` (or the loop that appends and starts, then the join loop): the body of `w` is
    inlined into `for k in _ail_par_range(0, T, T)`. Joining in the same block makes the threads scoped:
    what they are given is borrowed until the join, so `w` may read any list and write `out[k]` only.

Everything else -- and every program for which a check fails -- is returned as written, so threadlib.py
builds it on the general path under its lock, exactly as before; `notes` gets the reason and a
`write instead:` line. A program that names none of the modules is returned unchanged, byte for byte.
"""
import ast
import copy

import parallel

WORDS = ('concurrent', 'multiprocessing', 'threading')
_HOW_FN = ('a module-level def whose parameters are annotated int or float, that returns int or float and '
           'only computes (no I/O, no lists, no globals written)')


_USED_OTHER = ('the future %r is used other than as %s.result()\n  write instead: use only %s.result(); '
               'the tasks have run to completion at the submit')


class _Refuse(Exception):
    def __init__(self, node, text):
        Exception.__init__(self, text)
        self.line = getattr(node, 'lineno', None) or 1
        self.text = text


class _U(Exception):
    """parallel.py raises this (its `Unsupported`); the text becomes the note."""


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return '.'.join(reversed(parts))
    return None


class _Imports:
    """The bindings of the three modules; anything else of theirs leaves the program to threadlib.py."""

    def __init__(self, tree):
        self.ctors = {}     # dotted spelling -> 'executor' | 'pool' | 'thread'
        self.ascomp = set()  # spellings of concurrent.futures.as_completed
        self.roots = set()  # every name these imports bind
        self.nodes = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                hit = [a for a in node.names if a.name.split('.')[0] in ('concurrent', 'multiprocessing', 'threading')]
                if not hit:
                    continue
                if len(hit) != len(node.names):
                    raise _Refuse(node, 'an import that mixes these modules with others')
                for a in hit:
                    if a.name == 'concurrent.futures':
                        base = a.asname or 'concurrent.futures'
                        self.ctors[base + '.ThreadPoolExecutor'] = 'executor'
                        self.ascomp.add(base + '.as_completed')
                    elif a.name == 'multiprocessing':
                        self.ctors[(a.asname or a.name) + '.Pool'] = 'pool'
                    elif a.name == 'threading':
                        self.ctors[(a.asname or a.name) + '.Thread'] = 'thread'
                    else:
                        raise _Refuse(node, 'import %s' % a.name)
                    self.roots.add(a.asname or a.name.split('.')[0])
                self.nodes.append(node)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module in (
                    'concurrent.futures', 'multiprocessing', 'threading', 'concurrent'):
                want = {'concurrent.futures': 'ThreadPoolExecutor', 'multiprocessing': 'Pool',
                        'threading': 'Thread'}.get(node.module)
                for a in node.names:
                    if node.module == 'concurrent.futures' and a.name == 'as_completed':
                        self.ascomp.add(a.asname or a.name)
                        self.roots.add(a.asname or a.name)
                        continue
                    if a.name != want:
                        raise _Refuse(node, 'from %s import %s' % (node.module, a.name))
                    self.ctors[a.asname or a.name] = {'ThreadPoolExecutor': 'executor', 'Pool': 'pool',
                                                      'Thread': 'thread'}[want]
                    self.roots.add(a.asname or a.name)
                self.nodes.append(node)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in self.nodes:
                names = [a.name for a in node.names]
                mod = getattr(node, 'module', None) or ''
                if any(n.split('.')[0] in ('concurrent', 'multiprocessing', 'threading') for n in names) or \
                        mod.split('.')[0] in ('concurrent', 'multiprocessing', 'threading'):
                    raise _Refuse(node, 'an import of these modules inside a function')

    def kind(self, call):
        if isinstance(call, ast.Call):
            return self.ctors.get(_dotted(call.func))
        return None


def _stored(nodes):
    out = set()
    for stmt in nodes:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                out.add(n.id)
            elif isinstance(n, ast.arg):
                out.add(n.arg)
    return out


def _mentions(nodes, name):
    return any(isinstance(n, ast.Name) and n.id == name for stmt in nodes for n in ast.walk(stmt))


def _ann(node):
    """'int' / 'float' / 'list[int]' / 'list[float]' / 'bytearray' / None for an annotation."""
    if isinstance(node, ast.Name) and node.id in ('int', 'float', 'bytearray', 'bytes'):
        return node.id
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'list'
            and isinstance(node.slice, ast.Name) and node.slice.id in ('int', 'float')):
        return 'list[%s]' % node.slice.id
    return None


class _Pass:
    def __init__(self, tree, imports):
        self.tree, self.imp = tree, imports
        self.funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.helpers = []          # (top-level statement it must precede, helper source)
        self.k = 0
        self.top = None            # the top-level statement being rewritten
        self.done = []             # what was lowered (for the report)
        self.targets = set()       # thread functions inlined into a region
        self.pool_names = set()    # names bound to an executor or a pool

    # -- the function a map runs ----------------------------------------------------------------
    def scalar_fn(self, node, nargs, where):
        if not isinstance(node, ast.Name) or node.id not in self.funcs:
            raise _Refuse(where, 'map(%s, ...): the function is not a module-level def' % ast.unparse(node))
        fn = self.funcs[node.id]
        if len(fn.args.args) != nargs:
            raise _Refuse(where, 'map(%s, ...): %s() takes %d arguments, map gives it %d'
                          % (fn.name, fn.name, len(fn.args.args), nargs))
        try:
            parallel.check_callee(fn, self.funcs, _U, ())
        except _U as exc:
            raise _Refuse(where, '%s() cannot run without the lock: %s\n  write instead: %s' % (
                fn.name, str(exc).replace('parallel for: ', ''), _HOW_FN))
        return fn

    def workers(self, call, kind, pre, where):
        """The worker cap of an executor or pool constructor: an int expression (0: the default)."""
        name = 'max_workers' if kind == 'executor' else 'processes'
        args, kws = list(call.args), {k.arg: k.value for k in call.keywords}
        if None in kws:
            raise _Refuse(where, '**kwargs in the constructor')
        allowed = {'executor': ('max_workers', 'thread_name_prefix'), 'pool': ('processes', 'maxtasksperchild')}[kind]
        for key in kws:
            if key not in allowed:
                raise _Refuse(where, '%s= in the constructor' % key)
        if len(args) > 1:
            raise _Refuse(where, 'more than one positional argument in the constructor')
        value = args[0] if args else kws.get(name)
        if value is None or isinstance(value, ast.Constant) and value.value is None:
            return ast.Constant(value=0)
        if isinstance(value, ast.Constant) and type(value.value) is int:
            if value.value <= 0:
                raise _Refuse(where, '%s=%d (CPython raises ValueError)' % (name, value.value))
            return value
        self.k += 1
        temp = '_ail_workers%d' % self.k
        msg = 'max_workers must be greater than 0' if kind == 'executor' else 'Number of processes must be at least 1'
        pre.extend(ast.parse('%s = %s\nif %s <= 0:\n    raise ValueError(%r)\n'
                             % (temp, ast.unparse(value), temp, msg)).body)
        return ast.Name(id=temp, ctx=ast.Load())

    # -- one map call -----------------------------------------------------------------------------
    def lower_map(self, call, kind, cap, where):
        args = list(call.args)
        kws = {k.arg: k.value for k in call.keywords}
        for key in kws:
            if key != 'chunksize':
                raise _Refuse(where, 'map(..., %s=)' % key)
        if kind == 'pool':
            if len(args) == 3:
                args = args[:2]                     # chunksize: how work is dealt out, not what is computed
            if len(args) != 2:
                raise _Refuse(where, 'Pool.map takes a function and one iterable')
        elif not 2 <= len(args) <= 3:
            raise _Refuse(where, 'map over %d iterables' % (len(args) - 1))
        for value in [*args, *kws.values()]:
            if isinstance(value, ast.Starred):
                raise _Refuse(where, 'map(*args)')
        plan = self.map_plan(args[0], len(args) - 1, where)
        if plan is not None:
            return self.lower_map_tuples(plan, args[1:], cap, kind, where)
        fn = self.scalar_fn(args[0], len(args) - 1, where)
        its = args[1:]
        self.k += 1
        name = '_ail_pmap%d' % self.k
        params, call_args, lens, reads = [], [], [], []
        for j, (it, a) in enumerate(zip(its, fn.args.args)):
            t = a.annotation.id
            if (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range'
                    and 'range' not in self.funcs and 1 <= len(it.args) <= 2 and not it.keywords
                    and not any(isinstance(x, ast.Starred) for x in it.args)):
                lo, hi = (it.args[0], it.args[1]) if len(it.args) == 2 else (ast.Constant(value=0), it.args[0])
                params += ['lo%d: int' % j, 'hi%d: int' % j]
                call_args += [ast.unparse(lo), ast.unparse(hi)]
                lens.append('hi%d - lo%d' % (j, j))
                reads.append(('lo%d + i' % j) if t == 'int' else ('float(lo%d + i)' % j))
            else:
                params.append('a%d: list[%s]' % (j, t))
                # a list as it is; any other iterable (range with a step, a tuple) as the list of its values
                as_list = isinstance(it, (ast.Name, ast.List, ast.ListComp, ast.Subscript, ast.Attribute)) or (
                    isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'list')
                call_args.append(ast.unparse(it) if as_list else 'list(%s)' % ast.unparse(it))
                lens.append('len(a%d)' % j)
                reads.append('a%d[i]' % j)
        ret = fn.returns.id.replace('__ail_checked_', '').strip('_')
        zero = '0' if ret == 'int' else '0.0'
        lines = ['def %s(%s, workers: int) -> list[%s]:' % (name, ', '.join(params), ret),
                 '    n = %s' % lens[0]]
        for extra in lens[1:]:
            lines += ['    if %s < n:' % extra, '        n = %s' % extra]
        lines += ['    if n < 0:', '        n = 0',
                  '    r: list[%s] = [%s] * n' % (ret, zero),
                  '    for i in _ail_par_range(0, n, workers):',
                  '        r[i] = %s(%s)' % (fn.name, ', '.join(reads)),
                  '    return r']
        self.helpers.append((self.top, '\n'.join(lines) + '\n'))
        self.done.append((getattr(where, 'lineno', 1), '%s.map(%s)' % (kind, fn.name)))
        return ast.Call(func=ast.Name(id=name, ctx=ast.Load()),
                        args=[*(ast.parse(a, mode='eval').body for a in call_args), copy.deepcopy(cap)], keywords=[])

    # -- statements ---------------------------------------------------------------------------------
    def block(self, stmts, pools):
        out = []
        i = 0
        while i < len(stmts):
            s = stmts[i]
            used = self.threads(stmts, i, out)
            if used:
                i += used
                continue
            used = self.futures(stmts, i, out, pools)
            if used:
                i += used
                continue
            if (isinstance(s, ast.With) and len(s.items) == 1 and self.imp.kind(s.items[0].context_expr)
                    in ('executor', 'pool')):
                item = s.items[0]
                kind = self.imp.kind(item.context_expr)
                pre = []
                cap = self.workers(item.context_expr, kind, pre, s)
                inner = dict(pools)
                if item.optional_vars is not None:
                    if not isinstance(item.optional_vars, ast.Name):
                        raise _Refuse(s, 'with ... as (a pattern)')
                    inner[item.optional_vars.id] = (kind, cap)
                    self.pool_names.add(item.optional_vars.id)
                out.extend(pre)
                out.extend(self.block(s.body, inner))
                i += 1
                continue
            if (isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)
                    and self.imp.kind(s.value) in ('executor', 'pool')):
                kind = self.imp.kind(s.value)
                pre = []
                pools[s.targets[0].id] = (kind, self.workers(s.value, kind, pre, s))
                self.pool_names.add(s.targets[0].id)
                out.extend(pre)
                i += 1
                continue
            if (isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Attribute)
                    and isinstance(s.value.func.value, ast.Name) and s.value.func.value.id in pools
                    and s.value.func.attr in ('shutdown', 'close', 'join', 'terminate')):
                i += 1                                   # the work is done at each map; nothing to wait for
                continue
            for field in ('body', 'orelse', 'finalbody'):
                if isinstance(getattr(s, field, None), list) and not isinstance(s, (ast.FunctionDef, ast.ClassDef)):
                    setattr(s, field, self.block(getattr(s, field), pools))
            if isinstance(s, ast.Try):
                for h in s.handlers:
                    h.body = self.block(h.body, pools)
            if isinstance(s, ast.Match):
                for c in s.cases:
                    c.body = self.block(c.body, pools)
            out.extend(self.exprs(s, pools))
            out.append(s)
            i += 1
        return out or ([ast.Pass()] if stmts else out)

    def exprs(self, stmt, pools):
        """Rewrite `ex.map(...)` inside one statement (not inside its nested statement lists); the statements
        that must run before it."""
        hoisted = []
        parents = {}
        stack = [stmt]
        while stack:
            node = stack.pop()
            for field, value in ast.iter_fields(node):
                if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
                    continue
                for child in (value if isinstance(value, list) else [value]):
                    if isinstance(child, ast.AST):
                        parents[child] = node
                        stack.append(child)
        for node in list(parents):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id in pools):
                continue
            kind, cap = pools[node.func.value.id]
            if node.func.attr == 'submit':
                raise _Refuse(node, '%s.submit() in a shape that is not lowered: only futs = [ex.submit(f, ...) for v in xs] '
                                    '(or futs = [] and a loop that appends ex.submit(f, ...)), and names bound by '
                                    'consecutive f1 = ex.submit(f, ...) statements, whose futures are used only as '
                                    'fu.result() (in for / comprehensions over futs or as_completed(futs))\n  write '
                                    'instead: %s.map(f, xs) with the arguments in lists (results come back in order)'
                              % (node.func.value.id, node.func.value.id))
            if node.func.attr != 'map':
                raise _Refuse(node, '%s.%s() is not built without the lock yet\n  write instead: %s.map(f, xs) with the '
                                    'arguments in lists (results come back in order)' % (
                    node.func.value.id, node.func.attr, node.func.value.id))
            parent = parents[node]
            if kind == 'executor' and not self.consumed(node, parent):
                raise _Refuse(node, 'the iterator executor.map returns is used as a value\n  write instead: '
                                    'list(ex.map(f, xs)), or use it directly in for / sum / sorted / min / max')
            if kind == 'executor' and isinstance(parent, ast.For) and parent is stmt and parent.iter is node:
                hoisted.extend(self.lower_for_map(parent, node, cap))
                continue
            if kind == 'executor' and isinstance(parent, ast.comprehension):
                self.pure_comprehension(parent, parents, node)
            new = self.lower_map(node, kind, cap, node)
            if self.hoistable(stmt, node, parents):
                # bound to a name first (the typed path walks a name; `sorted(f(...))` it does not)
                temp = '_ail_mapped%d' % self.k
                hoisted.append(ast.Assign(targets=[ast.Name(id=temp, ctx=ast.Store())], value=new))
                new = ast.Name(id=temp, ctx=ast.Load())
            for field, value in ast.iter_fields(parent):
                if value is node:
                    setattr(parent, field, new)
                elif isinstance(value, list):
                    value[:] = [new if v is node else v for v in value]
        return hoisted

    @staticmethod
    def hoistable(stmt, node, parents):
        """Whether the map can run just before the statement: it runs once, unconditionally, and nothing the
        statement evaluates before it can be told apart (no other call of a user function or method)."""
        if isinstance(stmt, (ast.While, ast.With, ast.Try, ast.Match)) or (
                isinstance(stmt, ast.For) and not any(n is node for n in ast.walk(stmt.iter))):
            return False
        safe = {'list', 'tuple', 'sum', 'sorted', 'min', 'max', 'set', 'len', 'print', 'int', 'float', 'str',
                'abs', 'round', 'range', 'bool'}
        inside = {id(n) for n in ast.walk(node)}
        for n in ast.walk(stmt):
            if id(n) in inside or n is stmt:
                continue
            if isinstance(n, ast.Call) and not (isinstance(n.func, ast.Name) and n.func.id in safe):
                return False
            if isinstance(n, (ast.Lambda, ast.IfExp, ast.BoolOp, ast.Await, ast.Yield, ast.YieldFrom,
                              ast.NamedExpr)):
                return False
        child, up = node, parents.get(node)
        while up is not None and up is not stmt:
            if isinstance(up, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
                first = up.generators[0]
                if not (parents.get(child) is first and first.iter is child):
                    return False
            child, up = up, parents.get(up)
        return True

    @staticmethod
    def consumed(node, parent):
        """Whether the iterator is used up by something that sees only its values, in order."""
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and parent.args == [node] \
                and not parent.keywords and parent.func.id in ('list', 'tuple', 'sum', 'sorted', 'min', 'max', 'set'):
            return True
        if isinstance(parent, (ast.For, ast.comprehension)) and parent.iter is node:
            return True
        return False

    _PURE_CALLS = frozenset(('list', 'tuple', 'sum', 'sorted', 'min', 'max', 'set', 'len', 'int', 'float', 'str',
                             'abs', 'round', 'range', 'bool', 'divmod', 'pow', 'enumerate', 'zip'))

    def pure_comprehension(self, comp, parents, node):
        """`[g(r) for r in ex.map(f, xs)]`: CPython runs g on each result before f has run on the later items, so a
        g with effects (a print, an append) would show them before an exception of f; the map runs first here."""
        owner = parents.get(comp)
        parts = [n for n in ast.walk(owner) if n is not node]
        inside = {id(n) for n in ast.walk(node)}
        for n in parts:
            if id(n) in inside:
                continue
            if isinstance(n, ast.Call) and not (isinstance(n.func, ast.Name) and n.func.id in self._PURE_CALLS):
                raise _Refuse(n, 'a call inside a comprehension over executor.map: its effects would come before an '
                                 'exception of the map\n  write instead: rs = list(ex.map(f, xs)) first, then the '
                                 'comprehension over rs')

    def lower_for_map(self, loop, node, cap):
        """`for t in ex.map(f, xs[, ys]):` runs the body for the results before a failing item, as CPython does:
        the region runs first; if it raised, the loop calls f itself, one item at a time, so the exception comes at
        its item. Returns the statements that go before the loop (the loop is changed in place)."""
        if node.keywords or not 2 <= len(node.args) <= 3:
            raise _Refuse(node, 'map over %d iterables' % (len(node.args) - 1))
        fnode, its = node.args[0], node.args[1:]
        if not isinstance(fnode, ast.Name) or fnode.id not in self.funcs:
            raise _Refuse(node, 'map(%s, ...): the function is not a module-level def' % ast.unparse(fnode))
        fn = self.funcs[fnode.id]
        ret = _scalar_or_tuple(fn.returns)
        if ret is None:
            raise _Refuse(node, 'map(%s, ...): %s() must return int, float or a tuple of them' % (fn.name, fn.name))
        self.k += 1
        k = self.k
        pre, names = [], []
        for j, it in enumerate(its):
            nm = '_ail_x%d_%d' % (k, j)
            names.append(nm)
            is_range = (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range'
                        and 'range' not in self.funcs)
            as_list = isinstance(it, (ast.Name, ast.List, ast.ListComp, ast.Subscript, ast.Attribute)) or (
                isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'list')
            value = it if (as_list and not is_range) else ast.parse('list(0)', mode='eval').body
            if value is not it:
                value.args[0] = it
            pre.append(ast.Assign(targets=[ast.Name(id=nm, ctx=ast.Store())], value=value))
        call = ast.Call(func=node.func, args=[fnode] + [ast.Name(id=nm, ctx=ast.Load()) for nm in names], keywords=[])
        new = self.lower_map(call, 'executor', cap, node)
        rt, rk = ret
        rtype = ('tuple[%s]' % ', '.join([rt] * rk)) if rk else rt
        text = ('_ail_ok%d = True\n_ail_r%d: list[%s] = []\ntry:\n    _ail_r%d = 0\nexcept Exception:\n'
                '    _ail_ok%d = False\n' % (k, k, rtype, k, k))
        stmts = ast.parse(text).body
        stmts[2].body[0].value = new
        n_expr = 'len(%s)' % names[0]
        if len(names) == 2:
            pre.append(ast.parse('_ail_n%d = min(len(%s), len(%s))' % (k, names[0], names[1])).body[0])
            n_expr = '_ail_n%d' % k
        old_target = loop.target
        idx = '_ail_i%d' % k
        elems = ', '.join('%s[%s]' % (nm, idx) for nm in names)
        fetch = ast.parse('if _ail_ok%d:\n    T = _ail_r%d[%s]\nelse:\n    T = %s(%s)\n' % (
            k, k, idx, fn.name, elems)).body[0]
        fetch.body[0].targets[0] = copy.deepcopy(old_target)
        fetch.orelse[0].targets[0] = copy.deepcopy(old_target)
        loop.target = ast.Name(id=idx, ctx=ast.Store())
        loop.iter = ast.parse('range(%s)' % n_expr, mode='eval').body
        loop.body = [fetch] + loop.body
        return pre + stmts

    # -- tuples of int / float in and out of a map -------------------------------------------------------
    def map_plan(self, fnode, nargs, where):
        """(fn, params, ret) for a map function that takes or returns a tuple of ints or of floats (frozen
        values: a worker gets its own copy of the elements, nothing is shared); None when it has none."""
        if not isinstance(fnode, ast.Name) or fnode.id not in self.funcs:
            return None
        fn = self.funcs[fnode.id]
        if len(fn.args.args) != nargs or fn.args.defaults or fn.args.vararg or fn.args.kwonlyargs or fn.args.kwarg:
            return None
        params = [_scalar_or_tuple(a.annotation) for a in fn.args.args]
        ret = _scalar_or_tuple(fn.returns)
        if None in params or ret is None:
            return None
        if not any(p[1] for p in params) and not ret[1]:
            return None
        return fn, params, ret

    def lower_map_tuples(self, plan, its, cap, kind, where):
        fn, params, ret = plan
        self.k += 1
        k = self.k
        name = '_ail_pmap%d' % k
        # the callee's names are renamed into a private prefix so that they cannot meet the helper's own
        prefix = '_ail_p%d_' % k
        body = copy.deepcopy(fn.body)
        if isinstance(body[0] if body else None, ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        if not body or not isinstance(body[-1], ast.Return) or body[-1].value is None:
            raise _Refuse(where, '%s() must end with `return <value>`; a tuple-taking worker is run inline in the '
                                 'parallel loop' % fn.name)
        if any(isinstance(n, ast.Return) for st in body[:-1] for n in ast.walk(st)):
            raise _Refuse(where, '%s() returns early; the worker body is run inline\n  write instead: an if/else around '
                                 'the rest of the body and one return at the end' % fn.name)
        if any(isinstance(n, (ast.Global, ast.Nonlocal)) for st in body for n in ast.walk(st)):
            raise _Refuse(where, '%s() writes a module global; a worker may not' % fn.name)
        tuple_params = {a.arg: p for a, p in zip(fn.args.args, params) if p[1]}
        body = [_TupleUse(tuple_params, prefix).visit(st) for st in body]
        body = [x for st in body for x in (st if isinstance(st, list) else [st])]
        new_names = {a.arg: prefix + a.arg for a in fn.args.args if a.arg not in tuple_params}
        for n in _stored(body):
            if n not in tuple_params:
                new_names[n] = prefix + n
        for st in body:
            for n in ast.walk(st):
                if isinstance(n, ast.Name) and n.id in tuple_params:
                    raise _Refuse(where, '%s(): the tuple parameter %r is used other than as %s[0], %s[1], ... or '
                                         '`a, b = %s`\n  write instead: read its elements by index or unpack it'
                                  % (fn.name, n.id, n.id, n.id, n.id))
        body = [_Rename(new_names).visit(st) for st in body]
        final = body.pop()
        # the result: one list per element of a returned tuple
        rt, rk = ret
        if rk:
            if not (isinstance(final.value, ast.Tuple) and len(final.value.elts) == rk):
                raise _Refuse(where, '%s() must return a tuple display of %d elements, e.g. `return (a, b)`' % (fn.name, rk))
            stores = [ast.parse('r%d[i] = 0' % e).body[0] for e in range(rk)]
            for st, e in zip(stores, final.value.elts):
                st.value = e
        else:
            stores = [ast.parse('r0[i] = 0').body[0]]
            stores[0].value = final.value
        lines = []
        pnames, pcalls, lens = [], [], []
        for j, (a, (t, tk)) in enumerate(zip(fn.args.args, params)):
            pnames.append('a%d: list[%s]' % (j, ('tuple[%s]' % ', '.join([t] * tk)) if tk else t))
            lens.append('len(a%d)' % j)
        lines.append('def %s(%s, workers: int) -> list[%s]:' % (name, ', '.join(pnames), (
            'tuple[%s]' % ', '.join([rt] * rk)) if rk else rt))
        lines.append('    n = %s' % lens[0])
        for extra in lens[1:]:
            lines += ['    if %s < n:' % extra, '        n = %s' % extra]
        lines += ['    if n < 0:', '        n = 0']
        head = []
        for j, (a, (t, tk)) in enumerate(zip(fn.args.args, params)):
            if tk:
                for e in range(tk):
                    lines.append('    c%d_%d: list[%s] = [_t[%d] for _t in a%d]' % (j, e, t, e, j))
                    head.append('%s%s_%d: %s = c%d_%d[i]' % (prefix, a.arg, e, t, j, e))
            else:
                head.append('%s%s: %s = a%d[i]' % (prefix, a.arg, t, j))
        zero = '0' if rt == 'int' else '0.0'
        for e in range(max(rk, 1)):
            lines.append('    r%d: list[%s] = [%s] * n' % (e, rt, zero))
        lines.append('    for i in _ail_par_range(0, n, workers):')
        lines.append('        pass')
        tail = ['    return ' + ('[(%s) for j in range(n)]' % ', '.join('r%d[j]' % e for e in range(rk))
                                 if rk else 'r0')]
        src = '\n'.join(lines) + '\n' + '\n'.join(tail) + '\n'
        tree = ast.parse(src)
        fdef = tree.body[0]
        loop = [n for n in fdef.body if isinstance(n, ast.For)][0]
        loop.body = [ast.parse(h).body[0] for h in head] + body + stores
        try:
            trial = copy.deepcopy(loop)
            check = parallel._Body(trial, self.funcs, _U)
            check.block(trial.body, {check.var})
            check.check_owned()
        except _U as exc:
            raise _Refuse(where, '%s() cannot run without the lock: %s\n  write instead: %s' % (
                fn.name, str(exc).replace('parallel for: ', ''), _HOW_FN_TUPLE))
        ast.fix_missing_locations(tree)
        self.helpers.append((self.top, ast.unparse(tree) + '\n'))
        self.done.append((getattr(where, 'lineno', 1), '%s.map(%s)' % (kind, fn.name)))
        call_args = []
        for it, (t, tk) in zip(its, params):
            as_list = isinstance(it, (ast.Name, ast.List, ast.ListComp, ast.Subscript, ast.Attribute)) or (
                isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'list')
            call_args.append(ast.unparse(it) if as_list else 'list(%s)' % ast.unparse(it))
        return ast.Call(func=ast.Name(id=name, ctx=ast.Load()),
                        args=[*(ast.parse(a, mode='eval').body for a in call_args), copy.deepcopy(cap)], keywords=[])

    # -- submit / result ---------------------------------------------------------------------------------
    def submit_of(self, node, pools):
        """(call, cap) when `node` is `ex.submit(f, ...)` on a known executor, else None."""
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'submit'
                and isinstance(node.func.value, ast.Name) and pools.get(node.func.value.id, ('',))[0] == 'executor'):
            return node, pools[node.func.value.id][1]
        return None

    def stores(self, name):
        scope = self.top if isinstance(self.top, ast.FunctionDef) else self.tree
        return sum(1 for n in ast.walk(scope) if isinstance(n, ast.Name) and n.id == name
                   and isinstance(n.ctx, (ast.Store, ast.Del)))

    def submit_parts(self, call, where):
        if call.keywords or any(isinstance(a, ast.Starred) for a in call.args) or not call.args:
            raise _Refuse(where, 'submit(...) with keyword or starred arguments\n  write instead: ex.submit(f, a, b) '
                                 'with plain positional arguments')
        fn = self.scalar_fn(call.args[0], len(call.args) - 1, where)
        return fn, call.args[1:]

    def futures(self, stmts, i, out, pools):
        """Lower futures made by ex.submit and read with .result(): the tasks run as one parallel region at the
        statement that makes them (like map); a future is read only as `fu.result()`. If the region raises (a task
        failed), each .result() runs its task again on the calling thread, in order, so the exception comes out
        where CPython raises it, after the results before it were used. Number of statements used, or 0."""
        s = stmts[i]
        if not (isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)):
            return 0
        name, v = s.targets[0].id, s.value
        if self.submit_of(v, pools):
            return self.named_futures(stmts, i, out, pools)
        loop = None
        if (isinstance(v, ast.ListComp) and len(v.generators) == 1 and not v.generators[0].ifs
                and not v.generators[0].is_async and self.submit_of(v.elt, pools)):
            g = v.generators[0]
            call, cap = self.submit_of(v.elt, pools)
            target, it, used = g.target, g.iter, 1
        elif isinstance(v, ast.List) and not v.elts and i + 1 < len(stmts) and isinstance(stmts[i + 1], ast.For):
            loop = stmts[i + 1]
            body = loop.body
            if not (len(body) == 1 and isinstance(body[0], ast.Expr) and self.is_call(body[0].value, name, 'append')
                    and self.submit_of(body[0].value.args[0], pools) and not loop.orelse):
                return 0
            call, cap = self.submit_of(body[0].value.args[0], pools)
            target, it, used = loop.target, loop.iter, 2
        else:
            return 0
        names = [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]
        if not names:
            raise _Refuse(s, 'a submit loop over a pattern the typed path does not take')
        if self.stores(name) != 1:
            raise _Refuse(s, 'the list of futures %r is assigned more than once' % name)
        fn, cargs = self.submit_parts(call, s)
        rest = stmts[i + used:]
        if loop is not None and any(_mentions(rest, n) for n in names):
            raise _Refuse(loop, 'the loop variable is used after the loop that submits')
        self.k += 1
        k = self.k
        rename = {n: '_ail_v%d_%s' % (k, n) for n in names}
        tgt = _Rename(rename).visit(copy.deepcopy(target))
        cols = ['_ail_c%d_%d' % (k, j) for j in range(len(cargs))]
        types = [_ann(a.annotation) for a in fn.args.args]
        pre = ['_ail_n%d = 0' % k] + ['%s: list[%s] = []' % (c, t) for c, t in zip(cols, types)]
        body = [ast.parse('%s.append(None)' % c).body[0] for c in cols]
        for st, e in zip(body, cargs):
            st.value.args[0] = _Rename(rename).visit(copy.deepcopy(e))
        body.append(ast.parse('_ail_n%d += 1' % k).body[0])
        loop_node = ast.For(target=tgt, iter=copy.deepcopy(it), body=body, orelse=[], type_comment=None)
        region = self.region(k, fn, cols, '_ail_n%d' % k, cap, s)
        out.extend(ast.parse('\n'.join(pre)).body)
        out.append(loop_node)
        out.extend(region)
        self.rewrite_uses(rest, {name: ('list', k, fn, cols)}, s)
        return used

    def named_futures(self, stmts, i, out, pools):
        group, j = [], i
        ex = None
        while j < len(stmts):
            st = stmts[j]
            if not (isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name)):
                break
            got = self.submit_of(st.value, pools)
            if not got:
                break
            call, cap = got
            if ex is None:
                ex, cap0 = call.func.value.id, cap
            if call.func.value.id != ex:
                break
            group.append((st.targets[0].id, call, st))
            j += 1
        names = [g[0] for g in group]
        if len(set(names)) != len(names) or any(self.stores(n) != 1 for n in names):
            raise _Refuse(stmts[i], 'a future name is assigned more than once')
        fns = [self.submit_parts(call, st)[0] for n, call, st in group]
        if any(f.name != fns[0].name for f in fns):
            raise _Refuse(stmts[i], 'consecutive submits of different functions\n  write instead: ex.map over the '
                                    'arguments, or one group of submits per function')
        fn = fns[0]
        self.k += 1
        k = self.k
        cols = ['_ail_c%d_%d' % (k, c) for c in range(len(fn.args.args))]
        types = [_ann(a.annotation) for a in fn.args.args]
        out.extend(ast.parse('\n'.join('%s: list[%s] = []' % (c, t) for c, t in zip(cols, types)) or 'pass').body)
        for n, call, st in group:
            for c, e in zip(cols, call.args[1:]):
                stmt = ast.parse('%s.append(0)' % c).body[0]
                stmt.value.args[0] = e
                out.append(stmt)
        out.extend(self.region(k, fn, cols, str(len(group)), cap0, stmts[i]))
        index = {n: ('one', k, fn, cols, idx) for idx, n in enumerate(names)}
        self.rewrite_uses(stmts[j:], index, stmts[i])
        return j - i

    def region(self, k, fn, cols, n, cap, where):
        """The statements that run n tasks of fn over the columns in one parallel region."""
        params = ['n: int'] + ['a%d: list[%s]' % (c, _ann(a.annotation)) for c, a in enumerate(fn.args.args)]
        ret = fn.returns.id.replace('__ail_checked_', '').strip('_')
        zero = '0' if ret == 'int' else '0.0'
        lines = ['def _ail_psub%d(%s, workers: int) -> list[%s]:' % (k, ', '.join(params), ret),
                 '    r: list[%s] = [%s] * n' % (ret, zero),
                 '    for i in _ail_par_range(0, n, workers):',
                 '        r[i] = %s(%s)' % (fn.name, ', '.join('a%d[i]' % c for c in range(len(cols)))),
                 '    return r']
        self.helpers.append((self.top, '\n'.join(lines) + '\n'))
        self.done.append((getattr(where, 'lineno', 1), 'submit(%s)' % fn.name))
        call = '_ail_psub%d(%s, %s)' % (k, ', '.join([n] + cols), ast.unparse(cap))
        text = ('_ail_ok%d = True\n_ail_r%d: list[%s] = []\ntry:\n    _ail_r%d = %s\nexcept Exception:\n'
                '    _ail_ok%d = False\n' % (k, k, ret, k, call, k))
        return ast.parse(text).body

    def rewrite_uses(self, rest, futs, where):
        """In the statements after the submits: `fu.result()` of a future read in a for or a comprehension over
        the list (or as_completed(list)), `name.result()` of a named future, `len(list)`; any other use refuses."""
        owner = self
        listnames = {n for n, v in futs.items() if v[0] == 'list'}

        def count(f):
            return '_ail_n%d' % f[1]

        def res(f, idx):
            k, fn, cols = f[1], f[2], f[3]
            text = '(_ail_r%d[IDX] if _ail_ok%d else %s(%s))' % (
                k, k, fn.name, ', '.join('%s[IDX]' % c for c in cols))
            return ast.parse(text.replace('IDX', idx), mode='eval').body

        class T(ast.NodeTransformer):
            def __init__(self):
                self.env = {}

            def over(self, node):
                if isinstance(node, ast.Name) and node.id in listnames:
                    return futs[node.id]
                if (isinstance(node, ast.Call) and not node.keywords and len(node.args) == 1
                        and isinstance(node.args[0], ast.Name) and node.args[0].id in listnames
                        and _dotted(node.func) in owner.imp.ascomp):
                    return futs[node.args[0].id]
                return None

            def loop_head(self, target, it):
                f = self.over(it)
                if f is None:
                    return None
                if not isinstance(target, ast.Name):
                    raise _Refuse(where, 'a future list read through a pattern')
                return f, target.id, '_ail_i%d_%d' % (f[1], len(self.env))

            def visit_FunctionDef(self, node):
                for n in ast.walk(node):
                    if isinstance(n, ast.Name) and n.id in futs:
                        raise _Refuse(n, 'a future used inside a nested function')
                return node

            visit_AsyncFunctionDef = visit_Lambda = visit_FunctionDef

            def comp(self, node):
                added = []
                for g in node.generators:
                    got = self.loop_head(g.target, g.iter)
                    if got:
                        f, fu, idx = got
                        g.iter = ast.parse('range(%s)' % count(f), mode='eval').body
                        g.target = ast.Name(id=idx, ctx=ast.Store())
                        self.env[fu] = (f, idx)
                        added.append(fu)
                self.generic_visit(node)
                for fu in added:
                    del self.env[fu]
                    if any(isinstance(n, ast.Name) and n.id == fu for n in ast.walk(node)):
                        raise _Refuse(node, _USED_OTHER % (fu, fu, fu))
                return node

            visit_ListComp = visit_SetComp = visit_GeneratorExp = visit_DictComp = comp

            def visit_For(self, node):
                got = self.loop_head(node.target, node.iter)
                if not got:
                    return self.generic_visit(node)
                f, fu, idx = got
                node.iter = ast.parse('range(%s)' % count(f), mode='eval').body
                node.target = ast.Name(id=idx, ctx=ast.Store())
                self.env[fu] = (f, idx)
                node.body = [self.visit(x) for x in node.body]
                node.orelse = [self.visit(x) for x in node.orelse]
                del self.env[fu]
                if any(isinstance(n, ast.Name) and n.id == fu for st in node.body + node.orelse for n in ast.walk(st)):
                    raise _Refuse(node, _USED_OTHER % (fu, fu, fu))
                return node

            def visit_Call(self, node):
                if (isinstance(node.func, ast.Attribute) and node.func.attr == 'result' and not node.args
                        and not node.keywords and isinstance(node.func.value, ast.Name)):
                    n = node.func.value.id
                    if n in self.env:
                        f, idx = self.env[n]
                        return res(f, idx)
                    if n in futs and futs[n][0] == 'one':
                        return res(futs[n], str(futs[n][4]))
                if (isinstance(node.func, ast.Name) and node.func.id == 'len' and len(node.args) == 1
                        and isinstance(node.args[0], ast.Name) and node.args[0].id in listnames):
                    return ast.parse(count(futs[node.args[0].id]), mode='eval').body
                return self.generic_visit(node)

        t = T()
        for idx, st in enumerate(rest):
            rest[idx] = t.visit(st)
        for st in rest:
            for n in ast.walk(st):
                if isinstance(n, ast.Name) and n.id in futs:
                    raise _Refuse(n, 'the future %r is used other than as .result() (or len of the list of futures, or a '
                                     'for / comprehension over it or over as_completed)\n  write instead: use only '
                                     'fu.result(); the tasks run to completion at the submit' % n.id)

    # -- scoped threads ---------------------------------------------------------------------------------
    def threads(self, stmts, i, out):
        """Lower `ts = [Thread(...) for k in range(..)]`, the start loop and the join loop (or the loop that
        appends and starts, then the join loop); the number of statements used, or 0."""
        s = stmts[i]
        if not (isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)):
            return 0
        ts = s.targets[0].id
        made, used, late = None, 0, None
        v = s.value
        if (isinstance(v, ast.ListComp) and self.imp.kind(v.elt) == 'thread' and len(v.generators) == 1
                and not v.generators[0].ifs and isinstance(v.generators[0].target, ast.Name)):
            made, var, it, used = v.elt, v.generators[0].target.id, v.generators[0].iter, 1
            started = False
        elif isinstance(v, ast.List) and not v.elts and i + 1 < len(stmts):
            loop = stmts[i + 1]
            if not (isinstance(loop, ast.For) and isinstance(loop.target, ast.Name) and not loop.orelse):
                return 0
            var, it = loop.target.id, loop.iter
            body = loop.body
            started = False
            if (len(body) == 1 and isinstance(body[0], ast.Expr) and self.is_call(body[0].value, ts, 'append')
                    and self.imp.kind(body[0].value.args[0]) == 'thread'):
                made = body[0].value.args[0]
            elif (len(body) in (2, 3) and isinstance(body[0], ast.Assign) and len(body[0].targets) == 1
                  and isinstance(body[0].targets[0], ast.Name) and self.imp.kind(body[0].value) == 'thread'):
                t = body[0].targets[0].id
                rest = [ast.dump(x) for x in body[1:]]
                app = ast.dump(ast.Expr(value=ast.Call(func=ast.Attribute(value=ast.Name(id=ts, ctx=ast.Load()),
                               attr='append', ctx=ast.Load()), args=[ast.Name(id=t, ctx=ast.Load())], keywords=[])))
                start = ast.dump(ast.Expr(value=ast.Call(func=ast.Attribute(value=ast.Name(id=t, ctx=ast.Load()),
                                 attr='start', ctx=ast.Load()), args=[], keywords=[])))
                if rest == [app]:
                    pass
                elif rest in ([app, start], [start, app]):
                    started = True
                else:
                    return 0
                made = body[0].value
                late = (t, loop)
            else:
                return 0
            used = 2
        else:
            return 0
        j = i + used
        if not started:
            if not (j < len(stmts) and self.each(stmts[j], ts, 'start')):
                raise _Refuse(s, 'the threads in %r are not started by the next statement '
                                 '(for t in %s: t.start())' % (ts, ts))
            j += 1
        if not (j < len(stmts) and self.each(stmts[j], ts, 'join')):
            raise _Refuse(stmts[j] if j < len(stmts) else s,
                          'the threads in %r are not joined right after they are started; only threads started '
                          'and joined in one block run without the lock\n  write instead: for t in %s: t.join() '
                          'right after the loop that starts them, and do the other work after it' % (ts, ts))
        j += 1
        if _mentions(stmts[j:], ts):
            raise _Refuse(stmts[j - 1], '%r (the list of threads) is used after the join' % ts)
        if late and _mentions(stmts[j:], late[0]):
            raise _Refuse(late[1], 'the Thread variable %r is used after the join' % late[0])
        if _mentions(stmts[j:], var) and not isinstance(v, ast.ListComp):
            raise _Refuse(s, 'the loop variable %r is used after the join' % var)
        out.extend(self.inline_thread(made, var, it, s))
        return j - i

    @staticmethod
    def is_call(node, name, attr):
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attr
                and isinstance(node.func.value, ast.Name) and node.func.value.id == name
                and len(node.args) == (1 if attr == 'append' else 0) and not node.keywords)

    def each(self, stmt, ts, attr):
        return (isinstance(stmt, ast.For) and isinstance(stmt.iter, ast.Name) and stmt.iter.id == ts
                and isinstance(stmt.target, ast.Name) and len(stmt.body) == 1 and not stmt.orelse
                and isinstance(stmt.body[0], ast.Expr) and self.is_call(stmt.body[0].value, stmt.target.id, attr))

    def inline_thread(self, made, var, it, where):
        args = list(made.args)
        kws = {k.arg: k.value for k in made.keywords}
        if args:
            raise _Refuse(where, 'Thread(...) with positional arguments\n  write instead: Thread(target=f, args=(...))')
        for key in kws:
            if key not in ('target', 'args', 'name', 'daemon'):
                raise _Refuse(where, 'Thread(%s=...)' % key)
        target = kws.get('target')
        if not (isinstance(target, ast.Name) and target.id in self.funcs):
            raise _Refuse(where, 'the target is not a module-level def')
        fn = self.funcs[target.id]
        given = kws.get('args', ast.Tuple(elts=[], ctx=ast.Load()))
        if not isinstance(given, ast.Tuple) or any(isinstance(e, ast.Starred) for e in given.elts):
            raise _Refuse(where, 'args= that is not a tuple display')
        if (fn.args.vararg or fn.args.kwonlyargs or fn.args.defaults or fn.args.kwarg
                or len(fn.args.args) != len(given.elts)):
            raise _Refuse(where, '%s() takes other arguments than args= gives' % fn.name)
        if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range'
                and 1 <= len(it.args) <= 2 and not it.keywords):
            raise _Refuse(where, 'the threads are not made over range(n) or range(a, b)')
        if fn.returns is not None and not (isinstance(fn.returns, ast.Constant) and fn.returns.value is None):
            raise _Refuse(where, '%s() returns a value, which a Thread drops' % fn.name)
        body = copy.deepcopy(fn.body)
        if body and isinstance(body[-1], ast.Return) and body[-1].value is None:
            body = body[:-1]
        if isinstance(body[0] if body else None, ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        if any(isinstance(n, ast.Return) for st in body for n in ast.walk(st)):
            raise _Refuse(where, '%s() returns early; a scoped thread body cannot\n  write instead: an if/else '
                                 'around the rest of the body' % fn.name)
        if any(isinstance(n, (ast.Global, ast.Nonlocal)) for st in body for n in ast.walk(st)):
            raise _Refuse(where, '%s() writes a module global; threads without the lock may not\n  write instead: '
                                 'pass a list and write out[k], or return values through executor.map' % fn.name)
        self.k += 1
        loop = '_ail_t%d' % self.k
        locals_of_fn = _stored(body)
        enclosing = _stored(self.enclosing_body) | self.enclosing_params
        rename, head = {}, []
        for a, e in zip(fn.args.args, given.elts):
            kind = _ann(a.annotation)
            if kind is None:
                raise _Refuse(where, '%s(): parameter %r needs an annotation (int, float, list[int], '
                                     'list[float] or bytearray)' % (fn.name, a.arg))
            if isinstance(e, ast.Name) and e.id == var:
                if kind != 'int':
                    raise _Refuse(where, '%s(): parameter %r gets the thread index, so it must be int' % (fn.name, a.arg))
                rename[a.arg] = loop
            elif kind in ('int', 'float'):
                if a.arg not in locals_of_fn and isinstance(e, ast.Name) and e.id not in locals_of_fn:
                    rename[a.arg] = e.id                 # a value nobody writes while the threads run
                elif (a.arg not in locals_of_fn and isinstance(e, ast.Constant)
                      and type(e.value) in ((int,) if kind == 'int' else (int, float))):
                    rename[a.arg] = e
                else:
                    if any(isinstance(n, ast.Name) and n.id == var for n in ast.walk(e)):
                        e = _Rename({var: loop}).visit(copy.deepcopy(e))
                    fresh = '_ail_a%d_%s' % (self.k, a.arg)
                    rename[a.arg] = fresh
                    head.append(ast.AnnAssign(target=ast.Name(id=fresh, ctx=ast.Store()),
                                              annotation=ast.Name(id=kind, ctx=ast.Load()), value=e, simple=1))
            elif isinstance(e, ast.Name):
                if e.id in locals_of_fn - {a.arg}:
                    raise _Refuse(where, '%s(): the local %r has the name of the argument %r' % (fn.name, e.id, e.id))
                rename[a.arg] = e.id
            else:
                raise _Refuse(where, '%s(): a %s argument must be a name (it is shared with the thread, '
                                     'not copied)' % (fn.name, kind))
        free = {n.id for st in body for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        free -= locals_of_fn | {a.arg for a in fn.args.args}
        clash = sorted(n for n in free & enclosing if n not in self.funcs)
        if clash:
            raise _Refuse(where, '%s() reads the module name %s, which the calling function also binds'
                          % (fn.name, ', '.join(clash)))
        body = [_Rename(rename).visit(st) for st in body]
        lo, hi = (it.args[0], it.args[1]) if len(it.args) == 2 else (ast.Constant(value=0), it.args[0])
        self.k += 1
        lo_n, hi_n = '_ail_tlo%d' % self.k, '_ail_thi%d' % self.k
        pre = ast.parse('%s = %s\n%s = %s\n' % (lo_n, ast.unparse(lo), hi_n, ast.unparse(hi))).body
        if not body:
            return pre
        loop_node = ast.For(target=ast.Name(id=loop, ctx=ast.Store()),
                            iter=ast.Call(func=ast.Name(id='_ail_par_range', ctx=ast.Load()),
                                          args=[ast.Name(id=lo_n, ctx=ast.Load()), ast.Name(id=hi_n, ctx=ast.Load()),
                                                ast.BinOp(left=ast.Name(id=hi_n, ctx=ast.Load()), op=ast.Sub(),
                                                          right=ast.Name(id=lo_n, ctx=ast.Load()))],
                                          keywords=[]),
                            body=head + body, orelse=[], type_comment=None)
        # the race rules now, so that a body that breaks one is named here and left to the lock
        try:
            trial = copy.deepcopy(loop_node)
            check = parallel._Body(trial, self.funcs, _U)
            check.block(trial.body, {check.var})
            check.check_owned()
        except _U as exc:
            raise _Refuse(where, 'the thread function %s() cannot run without the lock: %s' % (
                fn.name, str(exc).replace('parallel for: ', '').replace('the loop variable', 'the thread index')
                .replace('(xs[i])', '(out[k], k the thread index)')
                + '\n  write instead: compute into locals and write out[k] once, k the thread index'))
        self.done.append((getattr(where, 'lineno', 1), 'Thread(target=%s)' % fn.name))
        self.targets.add(fn.name)
        return pre + [loop_node]


_HOW_FN_TUPLE = ('a module-level def whose parameters are int, float or a tuple of ints / of floats, that returns one of '
                'those and only computes (no I/O, no lists, no globals written), ending in one return')


def _norm(name):
    name = name.replace('__ail_checked_', '')
    return name[:-2] if name.endswith('__') else name


def _scalar_or_tuple(ann):
    """(elem, 0) for int / float, (elem, k) for tuple[elem, ... k times] of one numeric kind (what the typed path
    holds), else None."""
    if isinstance(ann, ast.Name) and _norm(ann.id) in ('int', 'float'):
        return _norm(ann.id), 0
    if (isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name) and _norm(ann.value.id) == 'tuple'
            and isinstance(ann.slice, ast.Tuple) and len(ann.slice.elts) >= 2
            and all(isinstance(e, ast.Name) and _norm(e.id) in ('int', 'float') for e in ann.slice.elts)
            and len({_norm(e.id) for e in ann.slice.elts}) == 1):
        return _norm(ann.slice.elts[0].id), len(ann.slice.elts)
    return None


class _TupleUse(ast.NodeTransformer):
    """In a worker body: `t[e]` of a tuple parameter becomes the private scalar of that element, and
    `a, b = t` becomes two assignments."""

    def __init__(self, tuples, prefix):
        self.tuples, self.prefix = tuples, prefix

    def elem(self, name, e):
        return ast.Name(id='%s%s_%d' % (self.prefix, name, e), ctx=ast.Load())

    def visit_Subscript(self, node):
        if (isinstance(node.value, ast.Name) and node.value.id in self.tuples
                and isinstance(node.ctx, ast.Load) and isinstance(node.slice, ast.Constant)
                and type(node.slice.value) is int and 0 <= node.slice.value < self.tuples[node.value.id][1]):
            return ast.copy_location(self.elem(node.value.id, node.slice.value), node)
        return self.generic_visit(node)

    def visit_Assign(self, node):
        if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple) and isinstance(node.value, ast.Name)
                and node.value.id in self.tuples and len(node.targets[0].elts) == self.tuples[node.value.id][1]
                and all(isinstance(t, ast.Name) for t in node.targets[0].elts)):
            return [ast.copy_location(ast.Assign(targets=[t], value=self.elem(node.value.id, e)), node)
                    for e, t in enumerate(node.targets[0].elts)]
        return self.generic_visit(node)


class _Rename(ast.NodeTransformer):
    def __init__(self, names):
        self.names = names

    def visit_Name(self, node):
        if node.id in self.names:
            new = self.names[node.id]
            if isinstance(new, ast.AST):                 # a constant argument, read only
                return ast.copy_location(copy.deepcopy(new), node)
            return ast.copy_location(ast.Name(id=new, ctx=node.ctx), node)
        return node


def rewrite_text(source, notes=None, report=None):
    """The program with its typed-parallel uses lowered, or the source as written (with a note)."""
    if not any(word in source for word in WORDS):
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    try:
        imports = _Imports(tree)
        if not imports.nodes:
            return source
        p = _Pass(tree, imports)
        for index, top in enumerate(list(tree.body)):
            p.top = top
            if isinstance(top, ast.FunctionDef):
                p.enclosing_body, p.enclosing_params = top.body, {a.arg for a in top.args.args}
                top.body = p.block(top.body, {})
            elif not isinstance(top, (ast.Import, ast.ImportFrom, ast.ClassDef)):
                p.enclosing_body, p.enclosing_params = [n for n in tree.body if not isinstance(n, ast.FunctionDef)], set()
                rewritten = p.block([top], {})
                if len(rewritten) != 1 or rewritten[0] is not top:
                    holder = ast.If(test=ast.Constant(value=True), body=rewritten, orelse=[])
                    tree.body[tree.body.index(top)] = holder
                    if p.helpers and p.helpers[-1][0] is top:
                        p.helpers = [(holder if t is top else t, h) for t, h in p.helpers]
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(imports.kind(n) for n in ast.walk(node)):
                raise _Refuse(node, 'a thread, executor or pool used inside a class')
            if isinstance(node, ast.Name) and node.id in p.pool_names:
                raise _Refuse(node, 'the executor or pool %r is used outside the block where it maps (or as a '
                                    'value)\n  write instead: call %s.map(...) inside its with block' % (node.id, node.id))
            if isinstance(node, ast.Name) and node.id in imports.roots and node not in imports.nodes:
                raise _Refuse(node, '%s is used in a way the typed path does not run without the lock (only Thread started '
                                    'and joined in one block, ThreadPoolExecutor.map and Pool.map are)\n  write instead: '
                                    'return results through executor.map, or give each thread its own out[k] '
                                    'instead of a lock or a queue' % node.id)
        if not p.done:
            return source
        tree.body = [n for n in tree.body if n not in imports.nodes]
        # a thread function whose body was inlined and that nothing else names is not compiled: the typed
        # path would refuse its list writes (a list parameter is read-only there), and nothing calls it
        named = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name in p.targets
                                                  and n.name not in named)]
        for top, text in p.helpers:
            at = tree.body.index(top) if top in tree.body else len(tree.body)
            tree.body[at:at] = ast.parse(text).body
        ast.fix_missing_locations(tree)
        text = ast.unparse(tree)
    except _Refuse as exc:
        if notes is not None:
            notes.append((exc.line, 'not run in parallel (it runs under the general path\'s lock): ' + exc.text))
        return source
    if report is not None:
        report.extend(p.done)
    return text.rstrip('\n') + '\n'


def general_text(source):
    """The general path runs a typed-parallel loop as the plain loop it stands for (same results; used
    only when the typed path refused something else in the program)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == parallel.PAR_ITER_CAP
                and len(node.args) == 3):
            node.func.id = 'range'
            node.args = node.args[:2]
    return ast.unparse(tree)
