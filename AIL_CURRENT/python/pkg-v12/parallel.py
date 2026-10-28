"""`parallel for i in range(a, b) { ... }` -- the compile-time half (checks and rewrite).

The brace front end spells it `for i in par_range(a, b)`. `prepare()` runs once per program, before
any other pass, and either refuses the loop by name or rewrites it into

    _par_lo1 = a;  _par_hi1 = b;
    for _par1_i in range(_par_lo1, _par_hi1):  # carries `.par`, the marker pyfunc._par_for reads
        body

with every name the body assigns renamed `_par<k>_<name>`. The body then compiles as an ordinary
loop; pyfunc moves its C text into a worker function (`_par_outline`) and cruntime's PAR part runs
that worker on several threads. This module only decides what such a body may contain.

The rule is that iterations cannot observe each other, so any schedule gives the sequential result.
The body may read anything and may write only
  * locals it assigns itself (each one must be assigned before it is read, in the body, and is
    invisible after the loop -- a read of it after the loop is refused),
  * elements `xs[i]`, `xs[i*K + j]` (j an inner `for j in range(0, K)`) or `xs[i*K + c]` (constants,
    c < K) of a list/bytearray -- indexes provably different for different `i`; every access to such
    a list in the body must use that same shape.
No append/pop/resize, no str/bytes/object values, no I/O, no raise/try/return, no calls except
the scalar builtins below and top-level fns that take and return only int/float and do nothing else
(recursively checked, no recursion). That keeps the body free of the runtime's non-thread-safe
state (arenas, reference counts, the cleanup chain, the exception stack).
"""
import ast
import copy

PAR_ITER = 'par_range'
# typedpar.py's spelling: `_ail_par_range(lo, hi, workers)`, the same loop on at most `workers` threads
# (ThreadPoolExecutor(max_workers=...).map, Pool(processes).map, joined Threads)
PAR_ITER_CAP = '_ail_par_range'
_BUILTINS = {'int': (1, 1), 'float': (1, 1), 'abs': (1, 1), 'min': (2, 2), 'max': (2, 2), 'round': (1, 1),
             'len': (1, 1), 'wrapping_add': (2, 2), 'wrapping_sub': (2, 2), 'wrapping_mul': (2, 2)}
_ARITH = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.LShift, ast.RShift,
          ast.BitAnd, ast.BitOr, ast.BitXor)
_HOW = ('; write results into a list or bytearray element indexed by the loop variable (xs[i]) and '
        'combine them after the loop')


def is_par(node):
    return (isinstance(node, ast.For) and isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name) and node.iter.func.id in (PAR_ITER, PAR_ITER_CAP))


def _refuse(Unsupported, node, message):
    error = Unsupported('parallel for: ' + message)
    line = getattr(node, 'lineno', None)
    if line is not None:
        error.source_line = line
    return error


class _Body:
    """Checks one loop body (and every function it calls); collects what the ownership proof needs."""

    def __init__(self, loop, funcs, Unsupported):
        self.loop, self.funcs, self.U = loop, funcs, Unsupported
        self.var = loop.target.id
        self.stored = set()
        for node in ast.walk(ast.Module(body=loop.body, type_ignores=[])):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                self.stored.add(node.id)
        self.stored.add(self.var)
        self.inner = {}        # inner loop variable -> [(lo, hi)] of the range() loops it drives
        self.assigned = set()  # names bound by an assignment (inner loop variables are not)
        self.reads, self.writes = {}, {}
        self.callees = set()

    def refuse(self, node, message):
        return _refuse(self.U, node, message)

    # -- statements -------------------------------------------------------------------------
    def block(self, stmts, defined):
        for stmt in stmts:
            defined = self.stmt(stmt, defined)
        return defined

    def bind(self, name):
        self.assigned.add(name)

    def stmt(self, s, defined):
        if isinstance(s, ast.Assign):
            if len(s.targets) != 1:
                raise self.refuse(s, 'chained assignment is not allowed')
            self.expr(s.value, defined)
            return self.store(s.targets[0], defined)
        if isinstance(s, ast.AnnAssign):
            ann = s.annotation
            if not (isinstance(ann, ast.Name) and ann.id in ('int', 'float')) or s.value is None:
                raise self.refuse(s, 'a local declared in the body must be an int or float with a value')
            self.expr(s.value, defined)
            return self.store(s.target, defined)
        if isinstance(s, ast.AugAssign):
            if not isinstance(s.op, _ARITH):
                raise self.refuse(s, 'unsupported operator')
            if isinstance(s.target, ast.Name):
                self.expr(s.target, defined)           # read-modify-write: must be defined already
            else:
                self.access(s.target, True, defined)
                self.access(s.target, False, defined)
            self.expr(s.value, defined)
            return self.store(s.target, defined, aug=True)
        if isinstance(s, ast.If):
            self.expr(s.test, defined)
            a = self.block(s.body, set(defined))
            b = self.block(s.orelse, set(defined))
            return defined | (a & b)
        if isinstance(s, ast.While):
            if s.orelse:
                raise self.refuse(s, 'while-else is not allowed')
            self.expr(s.test, defined)
            self.block(s.body, set(defined))
            return defined
        if isinstance(s, ast.For):
            if is_par(s):
                raise self.refuse(s, 'parallel for cannot be nested; make the inner loop an ordinary for')
            it = s.iter
            if (s.orelse or not isinstance(s.target, ast.Name) or not isinstance(it, ast.Call)
                    or not isinstance(it.func, ast.Name) or it.func.id != 'range' or it.keywords
                    or not 1 <= len(it.args) <= 3):
                raise self.refuse(s, 'inner loops must be `for j in range(...)`')
            for a in it.args:
                self.expr(a, defined)
            name = s.target.id
            if name == self.var:
                raise self.refuse(s, 'the loop variable cannot be reused by an inner loop')
            lo, hi = (it.args[0], it.args[1]) if len(it.args) > 1 else (ast.Constant(value=0), it.args[0])
            step = it.args[2] if len(it.args) == 3 else None
            self.inner.setdefault(name, []).append((lo, hi, step))
            self.block(s.body, defined | {name})
            return defined
        if isinstance(s, (ast.Break, ast.Continue, ast.Pass)):
            return defined
        if isinstance(s, ast.Expr):
            raise self.refuse(s, 'a call or expression statement (print, append, a helper) is not allowed; '
                                 'the body may only compute values' + _HOW)
        if isinstance(s, ast.Return):
            raise self.refuse(s, 'return is not allowed inside the body')
        raise self.refuse(s, '%s is not allowed in the body' % type(s).__name__.lower())

    def store(self, target, defined, aug=False):
        if isinstance(target, ast.Name):
            if target.id == self.var:
                raise self.refuse(target, 'the loop variable cannot be assigned')
            self.bind(target.id)
            return defined | {target.id}
        if isinstance(target, ast.Subscript):
            if not aug:
                self.access(target, True, defined)
            return defined
        raise self.refuse(target, 'only a local name or a list/bytearray element can be assigned')

    # -- expressions ------------------------------------------------------------------------
    def access(self, node, write, defined):
        base = node.value
        if not isinstance(base, ast.Name) or isinstance(node.slice, ast.Slice):
            raise self.refuse(node, 'only xs[index] on a plain name is allowed (no slices, fields or nested indexing)')
        if base.id in self.stored:
            raise self.refuse(node, '%r is assigned inside the body, so it cannot be indexed' % base.id)
        self.expr(node.slice, defined)
        (self.writes if write else self.reads).setdefault(base.id, []).append(node.slice)

    def expr(self, e, defined):
        if isinstance(e, ast.Constant):
            if isinstance(e.value, (int, float, bool)):
                return
            raise self.refuse(e, 'only int, float and bool constants are allowed (no str, bytes or None)')
        if isinstance(e, ast.Name):
            if e.id in self.stored and e.id not in defined:
                raise self.refuse(e, '%r is read before the body assigns it. Each iteration starts with fresh '
                                     'locals, so a value carried between iterations (a running total, a '
                                     'counter) is not allowed' % e.id + _HOW)
            return
        if isinstance(e, ast.BinOp):
            if not isinstance(e.op, _ARITH):
                raise self.refuse(e, 'unsupported operator')
            self.expr(e.left, defined)
            self.expr(e.right, defined)
            return
        if isinstance(e, ast.UnaryOp):
            self.expr(e.operand, defined)
            return
        if isinstance(e, ast.BoolOp):
            for v in e.values:
                self.expr(v, defined)
            return
        if isinstance(e, ast.Compare):
            if any(isinstance(op, (ast.In, ast.NotIn, ast.Is, ast.IsNot)) for op in e.ops):
                raise self.refuse(e, 'in / is comparisons are not allowed')
            self.expr(e.left, defined)
            for c in e.comparators:
                self.expr(c, defined)
            return
        if isinstance(e, ast.IfExp):
            for part in (e.test, e.body, e.orelse):
                self.expr(part, defined)
            return
        if isinstance(e, ast.Subscript):
            self.access(e, False, defined)
            return
        if isinstance(e, ast.Call):
            if not isinstance(e.func, ast.Name) or e.keywords:
                raise self.refuse(e, 'only plain calls of int/float/abs/min/max/round/len and of scalar fns are allowed')
            name = e.func.id
            if name == 'len':
                if len(e.args) != 1 or not isinstance(e.args[0], ast.Name) or e.args[0].id in self.stored:
                    raise self.refuse(e, 'len() takes a list or bytearray name')
                return
            if name in self.funcs:
                fn = self.funcs[name]
                if len(e.args) != len(fn.args.args):
                    raise self.refuse(e, '%s() takes %d arguments' % (name, len(fn.args.args)))
                check_callee(fn, self.funcs, self.U, ())
                self.callees.add(name)
            elif name in _BUILTINS:
                low, high = _BUILTINS[name]
                if not low <= len(e.args) <= high:
                    raise self.refuse(e, '%s() takes %d arguments' % (name, low))
            else:
                raise self.refuse(e, '%s() is not allowed: use int/float/abs/min/max/round or a fn over '
                                     'int and float only, which does nothing else' % name)
            for a in e.args:
                self.expr(a, defined)
            return
        raise self.refuse(e, '%s is not allowed in the body' % type(e).__name__.lower())

    # -- ownership of written elements -------------------------------------------------------
    def stride_ok(self, k):
        if isinstance(k, ast.Constant) and type(k.value) is int and k.value >= 1:
            return True
        return isinstance(k, ast.Name) and k.id not in self.stored

    def owned(self, index):
        """A key naming the family of indexes `index` belongs to when distinct iterations give
        distinct indexes (and 0 <= index for a loop starting at 0), else None."""
        if isinstance(index, ast.Name) and index.id == self.var:
            return ('i',)
        if isinstance(index, ast.BinOp) and isinstance(index.op, ast.Mult):
            for a, k in ((index.left, index.right), (index.right, index.left)):
                if (isinstance(a, ast.Name) and a.id == self.var and isinstance(k, ast.Constant)
                        and type(k.value) is int and k.value >= 1):
                    return ('stride', ast.dump(k))      # i * 4 is element 0 of row i of width 4
            return None
        if not (isinstance(index, ast.BinOp) and isinstance(index.op, ast.Add)):
            return None
        for stride, extra in ((index.left, index.right), (index.right, index.left)):
            if not (isinstance(stride, ast.BinOp) and isinstance(stride.op, ast.Mult)):
                continue
            for a, k in ((stride.left, stride.right), (stride.right, stride.left)):
                if not (isinstance(a, ast.Name) and a.id == self.var and self.stride_ok(k)):
                    continue
                if (isinstance(extra, ast.Constant) and type(extra.value) is int and extra.value >= 0
                        and isinstance(k, ast.Constant) and extra.value < k.value):
                    return ('stride', ast.dump(k))
                if (isinstance(extra, ast.Name) and extra.id not in self.assigned
                        and extra.id in self.inner and extra.id != self.var):
                    loops = self.inner[extra.id]
                    if all(step is None and isinstance(lo, ast.Constant) and type(lo.value) is int
                           and lo.value >= 0 and ast.dump(hi) == ast.dump(k) for lo, hi, step in loops):
                        return ('stride', ast.dump(k))
        return None

    def check_owned(self):
        for base, indexes in self.writes.items():
            keys = {self.owned(ix) for ix in indexes + self.reads.get(base, [])}
            if None in keys or len(keys) != 1:
                raise self.refuse(self.loop, '%r is written in the body, but not only at indexes that differ '
                                  'between iterations. Use %s[i], or %s[i * K + j] with j from an inner '
                                  '`for j in range(0, K)`, and touch %s nowhere else in the body'
                                  % (base, base, base, base))


def _is_extern(fn):
    """Whether fn is an `@extern(...)` stub for a foreign C function."""
    for d in fn.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        if isinstance(target, ast.Name) and target.id == 'extern':
            return True
    return False


def check_callee(fn, funcs, Unsupported, stack):
    """A fn callable from a parallel body: int/float parameters and result, locals only."""
    # A C function may keep state or call back into the runtime, so worker threads never run one.
    # Checked first: the annotation rule below refuses today's stubs only because they use C types,
    # which is not a promise
    if _is_extern(fn):
        raise _refuse(Unsupported, fn, 'extern %s() is a C function, so a parallel body cannot call it'
                                       % fn.name)
    if fn.name in stack:
        raise _refuse(Unsupported, fn, '%s() is recursive; a parallel body cannot call it' % fn.name)
    stack = stack + (fn.name,)
    bad = [a.arg for a in fn.args.args
           if not (isinstance(a.annotation, ast.Name) and a.annotation.id in ('int', 'float'))]
    if bad or fn.args.defaults or fn.args.vararg or fn.args.kwonlyargs:
        raise _refuse(Unsupported, fn, '%s() is called in a parallel body, so its parameters must be annotated '
                                       'int or float (found %s)' % (fn.name, ', '.join(bad) or 'defaults'))
    ret = fn.returns
    if not (isinstance(ret, ast.Name) and ret.id in ('int', 'float', '__ail_checked_int__', '__ail_checked_float__')):
        raise _refuse(Unsupported, fn, '%s() is called in a parallel body, so it must return int or float' % fn.name)
    checker = _Callee(fn, funcs, Unsupported, stack)
    checker.block(fn.body, {a.arg for a in fn.args.args})


class _Callee(_Body):
    """Same rules as a body, minus list access (a callee gets no containers) and plus `return`."""

    def __init__(self, fn, funcs, Unsupported, stack):
        loop = ast.For(target=ast.Name(id='\0', ctx=ast.Store()), iter=ast.Constant(value=0), body=fn.body,
                       orelse=[])
        super().__init__(loop, funcs, Unsupported)
        self.fn, self.stack = fn, stack
        self.stored = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        self.stored -= {a.arg for a in fn.args.args}

    def stmt(self, s, defined):
        if isinstance(s, ast.Return):
            if s.value is None:
                raise self.refuse(s, 'a bare return is not allowed here')
            self.expr(s.value, defined)
            return defined
        return super().stmt(s, defined)

    def access(self, node, write, defined):
        raise self.refuse(node, '%s() is called in a parallel body, so it cannot index a list' % self.fn.name)

    def expr(self, e, defined):
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in self.funcs:
            check_callee(self.funcs[e.func.id], self.funcs, self.U, self.stack)
            if len(e.args) != len(self.funcs[e.func.id].args.args):
                raise self.refuse(e, '%s() takes %d arguments' % (e.func.id, len(self.funcs[e.func.id].args.args)))
            for a in e.args:
                self.expr(a, defined)
            return
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == 'len':
            raise self.refuse(e, 'len() is not allowed in %s()' % self.fn.name)
        if isinstance(e, ast.Name) and e.id not in self.stored:
            return
        super().expr(e, defined)


def _loads(node, poisoned, Unsupported):
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in poisoned:
            raise _refuse(Unsupported, n, '%r is assigned inside a parallel body, so it is private to each '
                                          'iteration and has no value after the loop' % n.id + _HOW)


def _flow(stmts, poisoned, Unsupported):
    for s in stmts:
        poisoned = _flow_stmt(s, poisoned, Unsupported)
    return poisoned


def _flow_stmt(s, poisoned, U):
    if is_par(s) or hasattr(s, 'par'):
        _loads(s.iter, poisoned, U)
        return poisoned | s.par['private']
    if isinstance(s, (ast.Assign, ast.AnnAssign)):
        if s.value is not None:
            _loads(s.value, poisoned, U)
        targets = s.targets if isinstance(s, ast.Assign) else [s.target]
        cleared = set()
        for t in targets:
            if isinstance(t, ast.Name):
                cleared.add(t.id)
            else:
                _loads(t, poisoned, U)
        return poisoned - cleared
    if isinstance(s, ast.If):
        _loads(s.test, poisoned, U)
        return _flow(s.body, set(poisoned), U) | _flow(s.orelse, set(poisoned), U)
    if isinstance(s, (ast.While, ast.For)):
        head = s.test if isinstance(s, ast.While) else s.iter
        _loads(head, poisoned, U)
        target = set() if isinstance(s, ast.While) else {n.id for n in ast.walk(s.target) if isinstance(n, ast.Name)}
        first = _flow(s.body, poisoned - target, U)
        again = (poisoned | first) - target
        _loads(head, again, U)
        second = _flow(s.body, again, U)
        return _flow(s.orelse, poisoned | first | second, U)
    if isinstance(s, ast.Try):
        after = _flow(s.body, set(poisoned), U)
        for h in s.handlers:
            after = after | _flow(h.body, poisoned | after, U)
        after = after | _flow(s.orelse, set(after), U)
        return after | _flow(s.finalbody, poisoned | after, U)
    if isinstance(s, (ast.FunctionDef, ast.ClassDef)):
        return poisoned
    _loads(s, poisoned, U)
    return poisoned


def _rename(body, names, prefix):
    for stmt in body:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Name) and n.id in names:
                n.id = prefix + n.id


def _make(node, funcs, counter, U):
    it = node.iter
    cap = None
    if it.func.id == PAR_ITER_CAP:
        if it.keywords or len(it.args) != 3:
            raise _refuse(U, node, 'internal error: _ail_par_range takes (lo, hi, workers)')
        cap = it.args[2]
        it.args = it.args[:2]
    if it.keywords or len(it.args) not in (1, 2):
        raise _refuse(U, node, 'use range(stop) or range(start, stop); a step is not available')
    if not isinstance(node.target, ast.Name) or node.orelse:
        raise _refuse(U, node, 'the loop needs a single loop variable and no else branch')
    body = _Body(node, funcs, U)
    body.block(node.body, {body.var})
    body.check_owned()
    counter[0] += 1
    k = counter[0]
    lo, hi = (it.args[0], it.args[1]) if len(it.args) == 2 else (ast.Constant(value=0), it.args[0])
    private = set(body.stored)
    _rename(node.body, private, '_par%d_' % k)
    node.target.id = '_par%d_%s' % (k, node.target.id)
    lo_name, hi_name = '_par_lo%d' % k, '_par_hi%d' % k
    node.iter = ast.Call(func=ast.Name(id='range', ctx=ast.Load()),
                         args=[ast.Name(id=lo_name, ctx=ast.Load()), ast.Name(id=hi_name, ctx=ast.Load())],
                         keywords=[])
    node.par = {'k': k, 'private': private, 'lo': lo_name, 'hi': hi_name, 'callees': sorted(body.callees),
                'writes': sorted(body.writes)}
    pre = [ast.Assign(targets=[ast.Name(id=lo_name, ctx=ast.Store())], value=lo),
           ast.Assign(targets=[ast.Name(id=hi_name, ctx=ast.Store())], value=hi)]
    if cap is not None:
        node.par['cap'] = '_par_cap%d' % k
        pre.append(ast.Assign(targets=[ast.Name(id=node.par['cap'], ctx=ast.Store())], value=cap))
    for stmt in pre + [node]:
        ast.copy_location(stmt, node)
        ast.fix_missing_locations(stmt)
    return pre + [node]


def _transform(stmts, funcs, counter, U):
    out = []
    for s in stmts:
        if is_par(s):
            out.extend(_make(s, funcs, counter, U))
            continue
        if isinstance(s, ast.Try) and any(is_par(n) for n in ast.walk(s)):
            raise _refuse(U, s, 'parallel for cannot be inside try; put the loop in its own fn')
        for field in ('body', 'orelse', 'finalbody'):
            if isinstance(getattr(s, field, None), list):
                setattr(s, field, _transform(getattr(s, field), funcs, counter, U))
        out.append(s)
    return out


def prepare(tree, Unsupported):
    """Rewrite every `par_range` loop in `tree` (an ast.Module); a no-op for any other program."""
    if not any(is_par(n) for n in ast.walk(tree)):
        return 0
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and any(is_par(n) for n in ast.walk(node)):
            raise _refuse(Unsupported, node, 'not available in struct methods yet; use a top-level fn')
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    counter = [0]
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        if any(is_par(n) for n in ast.walk(fn)):
            fn.body = _transform(fn.body, funcs, counter, Unsupported)
            _flow(fn.body, set(), Unsupported)
    return counter[0]
