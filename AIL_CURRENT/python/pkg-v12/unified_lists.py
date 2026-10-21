# -*- coding: utf-8 -*-
"""unified_lists.py -- AIL_UNIFIED=1, step 2: the element types of lists (docs/design/UNIFIED_IR.md §9).

unified.py proves the types of local scalars. This pass proves, for the lists of the program, the type of every
element they can ever hold: `list[int]`, `list[float]`, `list[bool]`, and lists of such lists to any depth
(`list[list[int]]`, the grids). The representation does not change: a list is the general path's list object
(one object, shared by every name that holds it), so identity, aliasing and mutation keep Python's meaning by
construction. What the proof buys is the read: `grid[r][c]` indexes the vector in C and gives a C int64 / double
that unified.py's arithmetic takes as it is, with no runtime dispatch and no box.

The proof is Steensgaard-style unification over alias classes. Every place that can hold a list (a local, a
parameter, a function's result, an element of a list, a list display / comprehension / `[x] * n`) has a class;
assignments, arguments, returns and reads of an element unify classes, so all the names that can reach one list
object end in one class. A class is

    BOT   no value yet               N   only None (a list class may also hold None: `-> list[int] | None`)
    S(t)  scalars of type t          L   lists, with the class of their elements
    Pn    tuples of n components (step 3), with the class of each component    T  anything (unknown)

A store into a list (`xs[i] = v`, `xs.append(v)`, `xs[i] += v`, ...) unifies the element class with the stored
value's class. A list that reaches code this pass does not follow (an unknown function or method, a global, an
attribute, a tuple or dict, a lambda, a comparison with an object of unknown type, ...) is *escaped*: its class
becomes T, and so does the class of every list reachable from it, because that code may store anything there.
Only classes that end in L with an element class S(t) give typed reads; everything else is read as today.

The solution is recomputed in every round of unified.py's fixed point (the scalar types of stored values come from
there, and the element types read go back there); every state only rises, so the two settle together.
"""
import ast
import os

BOT = None
N, L, T = 'N', 'L', 'T'

_ARITH_INT = (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift,
              ast.RShift)
_ARITH_FLOAT = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)

# builtins that only read their arguments (no element of a list argument reaches anything else)
_READ_ONLY = {'len', 'print', 'str', 'repr', 'bool', 'id', 'isinstance', 'hash', 'format', 'ascii', 'abs', 'int',
              'float', 'round', 'chr', 'ord', 'range', 'divmod', 'pow', 'hex', 'oct', 'bin'}
# builtins that copy the elements of their arguments out (into a new container, an iterator, a result)
_COPY_OUT = {'sum', 'min', 'max', 'any', 'all', 'sorted', 'list', 'tuple', 'set', 'frozenset', 'enumerate',
             'zip', 'reversed', 'iter', 'next', 'dict'}
_LIST_READ_METHODS = {'count', 'index'}


def is_p(s):
    return isinstance(s, str) and len(s) > 1 and s[0] == 'P'


def combine(a, b):
    if a is BOT:
        return b
    if b is BOT:
        return a
    if a == T or b == T:
        return T
    if a == N:
        return b if b in (N, L) else T
    if b == N:
        return a if a == L else T
    if a == L and b == L:
        return L
    if a == L or b == L:
        return T
    return a if a == b else T


class UF(object):
    def __init__(self):
        self.parent = {}
        self.state = {}
        self.elem = {}
        self.comps = {}         # root -> the component classes of a tuple class (state 'P<n>')
        self.tab = {}           # root -> the rows of the one constant display all its lists come from, or False
        self.why = {}           # root -> the constraint that made it T (AIL_UNIFIED_LISTS_DEBUG)
        self.cur = None
        self.changed = False

    def find(self, k):
        if k not in self.parent:
            self.parent[k] = k
            self.state[k] = BOT
            return k
        root = k
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[k] != root:
            nxt = self.parent[k]
            self.parent[k] = root
            k = nxt
        return root

    def st(self, k):
        return self.state[self.find(k)]

    def _set(self, r, s):
        if self.state[r] != s:
            self.state[r] = s
            self.changed = True
            if s == T and r not in self.why:
                self.why[r] = self.cur

    def taint(self, k):
        r = self.find(k)
        old = self.state[r]
        if old == T:
            return
        self._set(r, T)
        if old == L:
            self.taint(self.elem[r])
        elif is_p(old):
            self.escape_comps(r)

    def escape(self, k, seen=None):
        """The value of class k reaches code this pass does not follow: a list there may be changed in any way
        (a tuple cannot change, but the lists in it can)."""
        r = self.find(k)
        s = self.state[r]
        if s == L:
            self.taint(k)
        elif is_p(s):
            self.escape_comps(r, seen)

    def escape_comps(self, r, seen=None):
        seen = set() if seen is None else seen
        r = self.find(r)
        if r in seen:
            return
        seen.add(r)
        for c in self.comps.get(r, ()):
            self.escape(c, seen)

    def give_p(self, k, comps):
        """Class k receives a tuple whose components have the classes `comps`."""
        r = self.find(k)
        old = self.state[r]
        n = 'P%d' % len(comps)
        new = combine(old, n)
        if new == T:
            self.taint(r)
            for c in comps:
                self.escape(c)
            return
        if is_p(old):
            for a, b in zip(self.comps[r], comps):
                self.unify(a, b)
            return
        self.comps[r] = list(comps)
        self._set(r, n)

    def set_tab(self, r, rows):
        old = self.tab.get(r)
        new = rows if old is None else (old if rows is None or rows == old else False)
        if new != old:
            self.tab[r] = new
            self.changed = True

    def mut(self, k):
        """A list of class k is changed in place (not a constant table any more)."""
        r = self.find(k)
        if self.state[r] == L:
            self.set_tab(r, False)

    def give(self, k, s, ek=None, rows=None):
        """Class k receives a value of state s (S(t), N, T, or L with element class ek; rows: see tab)."""
        r = self.find(k)
        old = self.state[r]
        new = combine(old, s)
        if new == T:
            self.taint(r)
            if s == L:
                self.taint(ek)
            return
        if new == L:
            if s == L:
                self.set_tab(r, rows if rows is not None else False)
            if old == L:
                if s == L:
                    self.unify(self.elem[r], ek)
                return
            self.elem[r] = ek
        self._set(r, new)

    def unify(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        sa, sb = self.state[ra], self.state[rb]
        ea, eb = self.elem.get(ra), self.elem.get(rb)
        s = combine(sa, sb)
        self.parent[rb] = ra
        if rb in self.tab:
            self.set_tab(ra, self.tab[rb])
        self.changed = True
        self.state[ra] = s if s != L else L
        if s == T:
            self.state[ra] = T
            if ra not in self.why:
                self.why[ra] = self.why.get(rb) or self.cur
            if sa == L:
                self.taint(ea)
            if sb == L:
                self.taint(eb)
            for st_, rr in ((sa, ra), (sb, rb)):
                if is_p(st_):
                    for c in self.comps.get(rr, ()):
                        self.escape(c)
            return
        if is_p(s):
            ca, cb = self.comps.get(ra), self.comps.get(rb)
            if is_p(sa) and is_p(sb):
                for x, y in zip(ca, cb):
                    self.unify(x, y)
            elif is_p(sb):
                self.comps[ra] = cb
            return
        if s == L:
            if sa == L and sb == L:
                self.elem[ra] = ea
                self.unify(ea, eb)
            else:
                self.elem[ra] = ea if sa == L else eb


def _arith(t, op, u):
    if t == 'int' and u == 'int' and isinstance(op, _ARITH_INT):
        return 'int'
    if t == 'int' and u == 'int' and isinstance(op, ast.Div):
        return 'float'
    if t in ('int', 'float') and u in ('int', 'float') and isinstance(op, _ARITH_FLOAT):
        return 'float'
    return None


def solve(cons):
    uf = UF()
    for _round in range(400):
        uf.changed = False
        for c in cons:
            op = c[0]
            uf.cur = c
            if op == 'eq':
                uf.unify(c[1], c[2])
            elif op == 'S':
                uf.give(c[1], ('S', c[2]))
            elif op == 'N':
                uf.give(c[1], N)
            elif op == 'T':
                uf.taint(c[1])
            elif op == 'L':
                uf.give(c[1], L, c[2], c[3] if len(c) > 3 else False)
            elif op == 'mut':
                uf.mut(c[1])
            elif op == 'elem':                  # c[1] := an element of c[2]
                s = uf.st(c[2])
                if s == L:
                    uf.unify(c[1], uf.elem[uf.find(c[2])])
                elif is_p(s):                   # iterating a tuple: any component
                    uf.taint(c[1])
                    uf.escape(c[2])
                elif s == T or isinstance(s, tuple):
                    uf.taint(c[1])
            elif op == 'P':                     # c[1] is a tuple display with the component classes c[2]
                uf.give_p(c[1], c[2])
            elif op == 'sub':                   # c[1] := c[2][c[3]] (c[3]: a constant int index, or None)
                s = uf.st(c[2])
                if s == L:
                    uf.unify(c[1], uf.elem[uf.find(c[2])])
                elif is_p(s):
                    n = int(s[1:])
                    i = c[3]
                    if i is not None and -n <= i < n:
                        uf.unify(c[1], uf.comps[uf.find(c[2])][i % n])
                    else:
                        uf.taint(c[1])
                        uf.escape(c[2])
                elif s == T or isinstance(s, tuple):
                    uf.taint(c[1])
            elif op == 'unpack':                # the names c[1] := the components of c[2] (`a, b = pair`)
                s = uf.st(c[2])
                if s is BOT or s == N:
                    pass
                elif s == L:
                    for v in c[1]:
                        uf.unify(v, uf.elem[uf.find(c[2])])
                elif is_p(s) and int(s[1:]) == len(c[1]):
                    for v, x in zip(c[1], uf.comps[uf.find(c[2])]):
                        uf.unify(v, x)
                else:
                    for v in c[1]:
                        uf.taint(v)
                    uf.escape(c[2])
            elif op == 'init':                  # an element of the new list c[1] (a display, a comprehension)
                s = uf.st(c[1])
                if s == L:
                    uf.unify(uf.elem[uf.find(c[1])], c[2])
                elif s == T or isinstance(s, tuple) or is_p(s):
                    uf.escape(c[2])
            elif op == 'store':                 # an element of c[1] := c[2]
                s = uf.st(c[1])
                if s == L:
                    uf.mut(c[1])
                    uf.unify(uf.elem[uf.find(c[1])], c[2])
                elif s == T or isinstance(s, tuple) or is_p(s):
                    uf.escape(c[2])
            elif op == 'store_elems':           # the elements of c[2] are added to c[1]
                a, b = uf.st(c[1]), uf.st(c[2])
                if a == L:
                    uf.mut(c[1])
                if a == L and b == L:
                    uf.unify(uf.elem[uf.find(c[1])], uf.elem[uf.find(c[2])])
                elif a not in (BOT, N) or b not in (BOT, N):
                    uf.taint(c[1])
                    uf.escape(c[2])
            elif op == 'augstore':              # an element of c[1] op= c[3]
                if uf.st(c[1]) == L:
                    uf.mut(c[1])
                    e = uf.elem[uf.find(c[1])]
                    se, sv = uf.st(e), uf.st(c[3])
                    if se is BOT or sv is BOT:
                        continue
                    t = _arith(se[1], c[2], sv[1]) if isinstance(se, tuple) and isinstance(sv, tuple) else None
                    if t is None:
                        uf.taint(e)
                    else:
                        uf.give(e, ('S', t))
                elif uf.st(c[1]) == T:
                    uf.escape(c[3])
            elif op == 'esc':
                uf.escape(c[1])
            elif op == 'cp':                    # the elements of c[1] are copied out to code not followed
                if uf.st(c[1]) == L:
                    uf.escape(uf.elem[uf.find(c[1])])
                elif is_p(uf.st(c[1])):
                    uf.escape(c[1])
            elif op == 'cmp':                   # compared: an unknown operand may run its own __eq__ on the others
                sts = [uf.st(k) for k in c[1]]
                if T in sts:
                    for k in c[1]:
                        uf.escape(k)
            elif op == 'cmp_in':                # c[1] is compared with each element of c[2] (`in`, .count, .index)
                s = uf.st(c[2])
                if s == L:
                    e = uf.elem[uf.find(c[2])]
                    if uf.st(c[1]) == T:
                        uf.escape(e)
                    if uf.st(e) == T:
                        uf.escape(c[1])
                elif s == T or is_p(s):
                    uf.escape(c[1])
                    uf.escape(c[2])
            elif op == 'copy_elems':            # c[1] is a new list holding the elements of c[2] (a slice, .copy())
                s = uf.st(c[2])
                if s == L and uf.st(c[1]) == L:
                    uf.unify(uf.elem[uf.find(c[1])], uf.elem[uf.find(c[2])])
                elif s == L:
                    uf.escape(uf.elem[uf.find(c[2])])
                elif s is not BOT and s != N:
                    uf.taint(c[1])
                    uf.escape(c[2])
            else:
                raise ValueError('unified_lists: unknown constraint %r' % (op,))
        if not uf.changed:
            return uf
    return None


def dump(uf, cons, path):
    """AIL_UNIFIED_LISTS_DEBUG=path: the classes of the program's variables, parameters and results, per round."""
    with open(path, 'a') as out:
        for k in sorted(uf.parent, key=str):
            if k[0] in ('v', 'p', 'r') and not str(k[1]).startswith(('pf__ail', 'pfu__ail', '_ail')):
                r = uf.find(k)
                e = uf.state.get(uf.find(uf.elem[r])) if r in uf.elem else ''
                ew = uf.why.get(uf.find(uf.elem[r])) if r in uf.elem else None
                out.write('%r %r tab=%r elem=%r why=%r ewhy=%r\n' % (k, uf.state[r], bool(uf.tab.get(r)), e,
                                                                     uf.why.get(r), ew))
        if os.environ.get('AIL_UNIFIED_LISTS_DEBUG_CONS'):
            for c in cons:
                out.write('  %r\n' % (c,))
        out.write('----\n')


class Gen(object):
    """The constraints of one analysed function body (unified.FnPlan)."""

    def __init__(self, plan, fp, cons, etype):
        self.plan = plan
        self.fp = fp
        self.cons = cons
        self.etype = etype
        self.keys = plan.lkey
        self.cur = {}

    def nk(self, node):
        k = ('x', self.fp.name, id(node))
        self.keys[(self.fp.name, id(node))] = k
        return k

    def top(self, node):
        k = self.nk(node)
        self.cons.append(('T', k))
        return k

    def var(self, name):
        return ('v', self.fp.name, name)

    def name_key(self, name, scope, node):
        if name in scope:
            k = scope[name]
        elif name in self.fp.locals:
            k = self.var(name)
        elif name in self.plan.gconst:
            k = self.nk(node)               # a module constant (unified.py): an int, a float or a bool
            self.cons.append(('S', k, self.plan.gconst[name]))
            return k
        else:
            return self.top(node)          # a global or a builtin: what it holds is not followed
        self.keys[(self.fp.name, id(node))] = k
        return k

    def esc(self, node, scope):
        self.cons.append(('esc', self.visit(node, scope)))

    def val(self, n, scope):
        """The class of n, in a context that keeps the value (it is stored, returned or passed on by a constraint of
        its own). Only here is a tuple display a tuple class; anywhere else its parts escape (see _visit)."""
        if isinstance(n, ast.Tuple) and isinstance(n.ctx, ast.Load) and not any(
                isinstance(e, ast.Starred) for e in n.elts):
            saved = self.cur
            self.cur = scope
            try:
                k = self.nk(n)
                comps = []
                for i, e in enumerate(n.elts):
                    ek = self.val(e, scope)
                    ck = ('tc', self.fp.name, id(n), i)
                    t = self.stype(e)
                    if t in ('int', 'float', 'bool'):
                        self.cons.append(('S', ck, t))
                    elif t is not BOT:
                        self.cons.append(('eq', ck, ek))
                    comps.append(ck)
                self.cons.append(('P', k, comps))
                return k
            finally:
                self.cur = saved
        return self.visit(n, scope)

    def stype(self, node):
        # the comprehension variables in scope have the types comp_scope gave them (a range target is an int);
        # every other name has unified.py's type
        over = {k[1]: v for k, v in self.cur.items() if isinstance(k, tuple) and k[0] == 't'}
        t = self.etype(node, over)
        return t if t in ('int', 'float', 'bool') else (BOT if t is None else 'obj')

    # ------------------------------------------------------------------ the body
    def run(self):
        fp = self.fp
        plan = self.plan
        info = fp.info
        closed = plan.closed
        fname = fp.pyname if not fp.is_method else None
        for i, p in enumerate(info['all_params']):
            v = self.var(p)
            if p in fp.lbad:
                continue
            if fp.spec and i < len(fp.ptypes) and fp.ptypes[i] in ('int', 'float', 'bool'):
                self.cons.append(('S', v, fp.ptypes[i]))
            elif fname in closed and p in info['params']:
                self.cons.append(('eq', v, ('p', fname, info['params'].index(p))))
            else:
                self.cons.append(('T', v))
        for v in fp.lbad:
            self.cons.append(('T', self.var(v)))
        self.ret_closed = fname in closed
        self.fname = fname
        if self.ret_closed and not _always_returns(fp.node.body):
            self.cons.append(('N', ('r', fname)))
        self.block(fp.node.body, {})

    def block(self, stmts, scope):
        for s in stmts:
            self.stmt(s, scope)

    def assign_to(self, tgt, vk, vnode, scope):
        """Class vk (of value vnode, or None) is stored into target tgt."""
        if isinstance(tgt, ast.Name):
            if tgt.id in self.fp.locals and tgt.id not in self.fp.lbad:
                self.cons.append(('eq', self.var(tgt.id), vk))
            else:
                self.cons.append(('esc', vk))
        elif isinstance(tgt, ast.Subscript):
            ck = self.visit(tgt.value, scope)
            if isinstance(tgt.slice, ast.Slice):
                for part in (tgt.slice.lower, tgt.slice.upper, tgt.slice.step):
                    if part is not None:
                        self.visit(part, scope)
                self.cons.append(('store_elems', ck, vk))
            else:
                self.visit(tgt.slice, scope)
                self.cons.append(('store', ck, vk))
        elif isinstance(tgt, (ast.Tuple, ast.List)):
            if isinstance(vnode, (ast.Tuple, ast.List)) and len(vnode.elts) == len(tgt.elts) and \
                    not any(isinstance(e, ast.Starred) for e in tgt.elts + vnode.elts):
                # `a, b = x, y` was visited element by element by the caller
                return
            names = [e for e in tgt.elts]
            if all(isinstance(e, ast.Name) and e.id in self.fp.locals and e.id not in self.fp.lbad for e in names) \
                    and len({e.id for e in names}) == len(names):
                self.cons.append(('unpack', [self.var(e.id) for e in names], vk))
                return
            self.cons.append(('cp', vk))
            for e in tgt.elts:
                self.assign_to(e.value if isinstance(e, ast.Starred) else e, self.top(e), None, scope)
        elif isinstance(tgt, ast.Attribute):
            self.visit(tgt.value, scope)
            self.cons.append(('esc', vk))
        else:
            self.cons.append(('esc', vk))

    def stmt(self, s, scope):
        if isinstance(s, (ast.Assign, ast.AnnAssign)):
            targets = s.targets if isinstance(s, ast.Assign) else [s.target]
            if s.value is None:
                return
            v = s.value
            if isinstance(v, (ast.Tuple, ast.List)) and isinstance(v.ctx, ast.Load) and all(
                    isinstance(t, (ast.Tuple, ast.List)) and len(t.elts) == len(v.elts) for t in targets) \
                    and not any(isinstance(e, ast.Starred) for e in v.elts) \
                    and not any(isinstance(e, ast.Starred) for t in targets for e in t.elts):
                ks = [self.val(e, scope) for e in v.elts]
                for t in targets:
                    for te, ke, ve in zip(t.elts, ks, v.elts):
                        self.assign_to(te, ke, ve, scope)
                return
            vk = self.val(v, scope)
            for t in targets:
                self.assign_to(t, vk, v, scope)
            return
        if isinstance(s, ast.AugAssign):
            vk = self.visit(s.value, scope)
            tg = s.target
            if isinstance(tg, ast.Name):
                if tg.id in self.fp.locals and tg.id not in self.fp.lbad:
                    virt = ast.BinOp(left=ast.Name(id=tg.id, ctx=ast.Load()), op=s.op, right=s.value)
                    t = self.stype(virt)
                    if t in ('int', 'float', 'bool'):
                        self.cons.append(('S', self.var(tg.id), t))
                    elif t is not BOT:
                        # `xs += ys` extends the list in place (and `xs` stays that list)
                        self.cons.append(('store_elems', self.var(tg.id), vk))
                else:
                    self.cons.append(('esc', vk))
            elif isinstance(tg, ast.Subscript) and not isinstance(tg.slice, ast.Slice):
                ck = self.visit(tg.value, scope)
                self.visit(tg.slice, scope)
                self.cons.append(('augstore', ck, s.op, vk))
            else:
                self.cons.append(('esc', vk))
                if isinstance(tg, ast.Subscript):
                    self.cons.append(('T', self.visit(tg.value, scope)))
                elif isinstance(tg, ast.Attribute):
                    self.visit(tg.value, scope)
            return
        if isinstance(s, ast.For):
            tg = s.target
            names = [e for e in tg.elts] if isinstance(tg, ast.Tuple) else None
            zargs = None
            if names and all(isinstance(e, ast.Name) and e.id in self.fp.locals and e.id not in self.fp.lbad
                             for e in names) and len({e.id for e in names}) == len(names):
                zargs = zip_call(self.plan, self.fp, s.iter, len(names))
                if zargs is None and len(names) == 2 and enum_call(self.plan, self.fp, s.iter):
                    # `for i, x in enumerate(xs)`: i is an int, x an element of xs; no tuple is kept
                    self.cons.append(('S', self.var(names[0].id), 'int'))
                    self.cons.append(('elem', self.var(names[1].id), self.visit(s.iter.args[0], scope)))
                    for a in s.iter.args[1:]:
                        self.visit(a, scope)
                    self.block(s.body, scope)
                    self.block(s.orelse, scope)
                    return
            if zargs is not None:
                # `for a, b in zip(xs, ys)`: the lists are read, one element each per step; no tuple is kept
                for e, a in zip(names, zargs):
                    self.cons.append(('elem', self.var(e.id), self.visit(a, scope)))
                self.block(s.body, scope)
                self.block(s.orelse, scope)
                return
            ik = self.visit(s.iter, scope)
            if isinstance(tg, ast.Name):
                if tg.id in self.fp.locals and tg.id not in self.fp.lbad:
                    v = self.var(tg.id)
                    if _is_range(s.iter, self.plan):
                        self.cons.append(('S', v, 'int'))
                    elif self.plan.const_iter(s.iter, 1, self.fp):
                        self.cons.append(('S', v, self.plan.const_iter(s.iter, 1, self.fp)))
                    else:
                        self.cons.append(('elem', v, ik))
                else:
                    self.cons.append(('cp', ik))
            else:
                # `for a, b in ...`: an int table of k-tuples gives ints; anything else is not followed
                ct = self.plan.const_iter(s.iter, len(tg.elts), self.fp) if isinstance(tg, ast.Tuple) else None
                if not ct and names and all(isinstance(e, ast.Name) and e.id in self.fp.locals
                                            and e.id not in self.fp.lbad for e in names) \
                        and len({e.id for e in names}) == len(names):
                    # `for a, b in xs`: each element of xs is unpacked into the names
                    ek = ('ue', self.fp.name, id(s))
                    self.cons.append(('elem', ek, ik))
                    self.cons.append(('unpack', [self.var(e.id) for e in names], ek))
                    self.block(s.body, scope)
                    self.block(s.orelse, scope)
                    return
                self.cons.append(('cp', ik))
                for x in ast.walk(tg):
                    if isinstance(x, ast.Name) and x.id in self.fp.locals and x.id not in self.fp.lbad:
                        self.cons.append(('S', self.var(x.id), ct) if ct else ('T', self.var(x.id)))
            self.block(s.body, scope)
            self.block(s.orelse, scope)
            return
        if isinstance(s, (ast.While, ast.If)):
            self.visit(s.test, scope)
            self.block(s.body, scope)
            self.block(s.orelse, scope)
            return
        if isinstance(s, ast.Return):
            if s.value is None:
                if self.ret_closed:
                    self.cons.append(('N', ('r', self.fname)))
                return
            vk = self.val(s.value, scope)
            if self.ret_closed:
                self.cons.append(('eq', ('r', self.fname), vk))
            else:
                self.cons.append(('esc', vk))
            return
        if isinstance(s, ast.Expr):
            self.visit(s.value, scope)
            return
        if isinstance(s, ast.Try):
            self.block(s.body, scope)
            for h in s.handlers:
                if h.type is not None:
                    self.esc(h.type, scope)
                self.block(h.body, scope)
            self.block(s.orelse, scope)
            self.block(s.finalbody, scope)
            return
        if isinstance(s, ast.With):
            for item in s.items:
                self.esc(item.context_expr, scope)
            self.block(s.body, scope)
            return
        if isinstance(s, ast.Delete):
            for t in s.targets:
                if isinstance(t, ast.Subscript):
                    self.cons.append(('mut', self.visit(t.value, scope)))
                    if isinstance(t.slice, ast.Slice):
                        for part in (t.slice.lower, t.slice.upper, t.slice.step):
                            if part is not None:
                                self.visit(part, scope)
                    else:
                        self.visit(t.slice, scope)
                elif isinstance(t, ast.Attribute):
                    self.visit(t.value, scope)
            return
        if isinstance(s, ast.Assert):
            self.visit(s.test, scope)
            if s.msg is not None:
                self.esc(s.msg, scope)
            return
        if isinstance(s, (ast.Pass, ast.Break, ast.Continue, ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom)):
            return
        # anything else (raise, match, try*, ...): every expression in it escapes, every statement is walked
        self.generic(s, scope)

    def generic(self, node, scope):
        for c in ast.iter_child_nodes(node):
            if isinstance(c, ast.expr):
                self.esc(c, scope)
            elif isinstance(c, ast.stmt):
                self.stmt(c, scope)
            else:
                self.generic(c, scope)

    # ------------------------------------------------------------------ expressions
    def visit(self, n, scope):
        saved = self.cur
        self.cur = scope
        try:
            return self._visit(n, scope)
        finally:
            self.cur = saved

    def _visit(self, n, scope):
        """The class key of expression n; the constraints of its parts."""
        if isinstance(n, ast.Name):
            return self.name_key(n.id, scope, n)
        if isinstance(n, ast.Constant):
            k = self.nk(n)
            if n.value is None:
                self.cons.append(('N', k))
            else:
                t = self.stype(n)
                self.cons.append(('S', k, t) if t in ('int', 'float', 'bool') else ('T', k))
            return k
        if isinstance(n, ast.Subscript) and self.plan.row_read(self.fp, n) not in (None, 'bot'):
            self.visit(n.value, scope)
            k = self.nk(n)
            self.cons.append(('S', k, 'int'))           # a column of a constant table row (unified.py)
            return k
        if isinstance(n, ast.Subscript):
            ck = self.visit(n.value, scope)
            if isinstance(n.slice, ast.Slice):
                for part in (n.slice.lower, n.slice.upper, n.slice.step):
                    if part is not None:
                        self.visit(part, scope)
                # a slice is a new list holding the same elements (or a str / tuple: then not a list class)
                k = self.nk(n)
                ek = ('xe', self.fp.name, id(n))
                self.cons.append(('L', k, ek))
                self.cons.append(('copy_elems', k, ck))
                return k
            self.visit(n.slice, scope)
            k = self.nk(n)
            it = self.stype(n.slice)
            if it in ('int', 'bool') or isinstance(n.slice, ast.Constant):
                # (a constant that is not an int is not a slice either: the read raises TypeError)
                self.cons.append(('sub', k, ck, _const_index(n.slice)))
            elif it is not BOT:
                # an index of unknown type may be a slice object: the value is then a new list of the elements
                self.cons.append(('cp', ck))
                self.cons.append(('T', k))
            return k
        if isinstance(n, ast.List) and isinstance(n.ctx, ast.Load):
            k = self.nk(n)
            ek = ('xe', self.fp.name, id(n))
            tr = self.plan.table_rows(n.elts)
            self.cons.append(('L', k, ek, tuple(tuple(r) for r in tr[1]) if tr else False))
            for e in n.elts:
                if isinstance(e, ast.Starred):
                    self.cons.append(('store_elems', k, self.visit(e.value, scope)))
                else:
                    self.cons.append(('init', k, self.val(e, scope)))
            return k
        if isinstance(n, ast.ListComp):
            inner = self.comp_scope(n, scope)
            k = self.nk(n)
            ek = ('xe', self.fp.name, id(n))
            self.cons.append(('L', k, ek))
            self.cons.append(('init', k, self.val(n.elt, inner)))
            return k
        if isinstance(n, (ast.SetComp, ast.GeneratorExp)):
            inner = self.comp_scope(n, scope)
            self.esc(n.elt, inner)
            return self.top(n)
        if isinstance(n, ast.DictComp):
            inner = self.comp_scope(n, scope)
            self.esc(n.key, inner)
            self.esc(n.value, inner)
            return self.top(n)
        if isinstance(n, ast.BinOp):
            if isinstance(n.op, ast.Mult) and (isinstance(n.left, ast.List) or isinstance(n.right, ast.List)):
                lst, cnt = (n.left, n.right) if isinstance(n.left, ast.List) else (n.right, n.left)
                lk = self.visit(lst, scope)
                self.cons.append(('mut', lk))
                self.visit(cnt, scope)
                self.keys[(self.fp.name, id(n))] = lk           # `[x] * n`: a new list whose elements are x's
                return lk
            a = self.visit(n.left, scope)
            b = self.visit(n.right, scope)
            t = self.stype(n)
            k = self.nk(n)
            if t in ('int', 'float', 'bool'):
                self.cons.append(('S', k, t))
            elif t is not BOT:
                # list + list, list * n, str % args, ...: a new value; the elements of a list operand are copied
                self.cons.append(('cp', a))
                self.cons.append(('cp', b))
                self.cons.append(('T', k))
            return k
        if isinstance(n, ast.UnaryOp):
            self.visit(n.operand, scope)
            return self.scalar_or_top(n)
        if isinstance(n, ast.Compare):
            ks = [self.visit(x, scope) for x in [n.left] + n.comparators]
            for i, op in enumerate(n.ops):
                if isinstance(op, (ast.In, ast.NotIn)):
                    self.cons.append(('cmp_in', ks[i], ks[i + 1]))      # x compared with each element of xs
                elif not isinstance(op, (ast.Is, ast.IsNot)):
                    self.cons.append(('cmp', [ks[i], ks[i + 1]]))
            return self.scalar_or_top(n)
        if isinstance(n, ast.BoolOp):
            k = self.nk(n)
            for v in n.values:
                self.cons.append(('eq', k, self.visit(v, scope)))
            return k
        if isinstance(n, ast.IfExp):
            self.visit(n.test, scope)
            k = self.nk(n)
            self.cons.append(('eq', k, self.visit(n.body, scope)))
            self.cons.append(('eq', k, self.visit(n.orelse, scope)))
            return k
        if isinstance(n, ast.Call):
            return self.call(n, scope)
        if isinstance(n, (ast.JoinedStr, ast.FormattedValue)):
            for c in ast.iter_child_nodes(n):
                if isinstance(c, ast.expr):
                    self.visit(c, scope)
            return self.top(n)
        if isinstance(n, ast.Lambda):
            # the body is code this pass does not follow: what it reads from the comprehension scope escapes
            for x in ast.walk(n.body):
                if isinstance(x, ast.Name) and x.id in scope:
                    self.cons.append(('esc', scope[x.id]))
            for d in n.args.defaults + [d for d in n.args.kw_defaults if d is not None]:
                self.esc(d, scope)
            return self.top(n)
        if isinstance(n, ast.Attribute):
            self.esc(n.value, scope)
            return self.top(n)
        # tuple / dict / set displays, starred, walrus, await, ...: the parts escape
        for c in ast.iter_child_nodes(n):
            if isinstance(c, ast.expr):
                self.esc(c, scope)
        return self.top(n)

    def scalar_or_top(self, n):
        k = self.nk(n)
        t = self.stype(n)
        if t in ('int', 'float', 'bool'):
            self.cons.append(('S', k, t))
        elif t is not BOT:
            self.cons.append(('T', k))
        return k

    def comp_scope(self, n, scope):
        inner = dict(scope)
        for g in n.generators:
            ik = self.visit(g.iter, inner)
            tg = g.target
            if isinstance(tg, ast.Name):
                ck = ('c', id(n), tg.id)
                if _is_range(g.iter, self.plan) and 'range' not in self.fp.locals:
                    self.cons.append(('S', ck, 'int'))
                    inner[('t', tg.id)] = 'int'
                else:
                    self.cons.append(('elem', ck, ik))
                    el = self.plan.lelem.get((self.fp.name, id(g.iter)))
                    inner[('t', tg.id)] = el if el in ('int', 'float', 'bool') else 'obj'
                inner[tg.id] = ck
            else:
                self.cons.append(('cp', ik))
                for x in ast.walk(tg):
                    if isinstance(x, ast.Name):
                        inner[x.id] = self.top(x)
                        inner[('t', x.id)] = 'obj'
            for c in g.ifs:
                self.visit(c, inner)
        return inner

    def call(self, n, scope):
        f = n.func
        plan = self.plan
        args = n.args
        if isinstance(f, ast.Name) and f.id in plan.closed and f.id not in scope and f.id not in self.fp.locals \
                and not n.keywords and len(args) == plan.closed[f.id] \
                and not any(isinstance(a, ast.Starred) for a in args):
            for i, a in enumerate(args):
                self.cons.append(('eq', self.val(a, scope), ('p', f.id, i)))
            self.keys[(self.fp.name, id(n))] = ('r', f.id)
            return ('r', f.id)
        builtin = isinstance(f, ast.Name) and f.id not in scope and plan.is_builtin(self.fp, f.id)
        if builtin and f.id in _READ_ONLY and not n.keywords:
            for a in args:
                self.visit(a.value if isinstance(a, ast.Starred) else a, scope)
            return self.scalar_or_top(n)
        if builtin and f.id in _COPY_OUT:
            for a in args:
                self.cons.append(('cp', self.visit(a.value if isinstance(a, ast.Starred) else a, scope)))
            for kw in n.keywords:
                self.esc(kw.value, scope)
            return self.scalar_or_top(n)
        if isinstance(f, ast.Attribute):
            rk = self.visit(f.value, scope)
            m = f.attr
            if m == 'append' and len(args) == 1 and not n.keywords and not isinstance(args[0], ast.Starred):
                self.cons.append(('store', rk, self.val(args[0], scope)))
                return self.top(n)
            if m == 'insert' and len(args) == 2 and not n.keywords:
                self.visit(args[0], scope)
                self.cons.append(('store', rk, self.val(args[1], scope)))
                return self.top(n)
            if m == 'extend' and len(args) == 1 and not n.keywords:
                self.cons.append(('store_elems', rk, self.visit(args[0], scope)))
                return self.top(n)
            if m == 'pop' and len(args) <= 1 and not n.keywords:
                for a in args:
                    self.visit(a, scope)
                self.cons.append(('mut', rk))
                k = self.nk(n)
                self.cons.append(('elem', k, rk))
                return k
            if m in _LIST_READ_METHODS and not n.keywords:
                ks = [self.visit(a, scope) for a in args]
                if ks:
                    self.cons.append(('cmp_in', ks[0], rk))
                return self.scalar_or_top(n)
            if m in ('reverse', 'clear') and not args and not n.keywords:
                self.cons.append(('mut', rk))
                return self.top(n)
            if m == 'remove' and len(args) == 1 and not n.keywords:
                self.cons.append(('mut', rk))
                self.cons.append(('cmp_in', self.visit(args[0], scope), rk))
                return self.top(n)
            if m == 'sort' and not args:
                self.cons.append(('mut', rk))
                for kw in n.keywords:
                    self.esc(kw.value, scope)
                if n.keywords:
                    self.cons.append(('cp', rk))
                return self.top(n)
            if m == 'copy' and not args and not n.keywords:
                k = self.nk(n)
                ek = ('xe', self.fp.name, id(n))
                self.cons.append(('L', k, ek))
                self.cons.append(('copy_elems', k, rk))
                return k
            # any other method: the receiver and the arguments reach code this pass does not follow
            self.cons.append(('esc', rk))
            for a in args:
                self.esc(a.value if isinstance(a, ast.Starred) else a, scope)
            for kw in n.keywords:
                self.esc(kw.value, scope)
            return self.scalar_or_top(n)
        if not isinstance(f, ast.Name):
            self.esc(f, scope)
        for a in args:
            self.esc(a.value if isinstance(a, ast.Starred) else a, scope)
        for kw in n.keywords:
            self.esc(kw.value, scope)
        return self.scalar_or_top(n)


def _const_index(sl):
    """The int of a constant (or negated constant) subscript, else None."""
    if isinstance(sl, ast.Constant) and type(sl.value) is int:
        return sl.value
    if isinstance(sl, ast.UnaryOp) and isinstance(sl.op, ast.USub) and isinstance(sl.operand, ast.Constant) \
            and type(sl.operand.value) is int:
        return -sl.operand.value
    return None


def enum_call(plan, fp, it):
    """`enumerate(xs)` / `enumerate(xs, <small int constant>)` (the builtin)."""
    if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'enumerate'
            and not it.keywords and not any(isinstance(a, ast.Starred) for a in it.args)
            and plan.is_builtin(fp, 'enumerate')):
        return False
    if len(it.args) == 1:
        return True
    return (len(it.args) == 2 and isinstance(it.args[1], ast.Constant) and type(it.args[1].value) is int
            and -(1 << 62) < it.args[1].value < (1 << 62))


def zip_call(plan, fp, it, k):
    """`zip(a, b, ...)` of k >= 2 plain positional arguments (the builtin), else None."""
    if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'zip' and not it.keywords \
            and len(it.args) == k and k >= 2 and not any(isinstance(a, ast.Starred) for a in it.args) \
            and plan.is_builtin(fp, 'zip'):
        return it.args
    return None


def _always_returns(stmts):
    for s in stmts:
        if isinstance(s, (ast.Return, ast.Raise)):
            return True
        if isinstance(s, ast.If) and s.orelse and _always_returns(s.body) and _always_returns(s.orelse):
            return True
    return False


def _is_range(n, plan):
    return (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'range'
            and 'range' not in plan.fn_names and not n.keywords)
