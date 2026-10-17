"""A named refusal for list/dict/set/bytearray aliasing in Python-syntax (def) files.

CPython binds `ys = xs` to the SAME object: a write through one name shows through the other. The
legacy emitter gives every name its own value (copies on assignment), so a program that writes
through one name and reads the other afterwards would print something else, silently. Until the
IR's sharing semantics (ir/ownership.py, design section 13) covers every function, a def-syntax
function that stays on the legacy emitter and has such a site is refused here instead, naming the
line and the copy spellings. Block-syntax files keep their value semantics (the W-ALIAS note).
(The refusal sends the whole program to the general path, which shares, unless that is switched off.)

What counts as "a second reference" -- every way a container value gets one more holder:

    ys = xs                      a second name
    zs = b.xs                    a field read into a name
    b.xs = ys   g[i] = xs        a field / element store
    g.append(xs)  g.insert(i, xs)  g.extend([xs])  g += [xs]   storing it in another container
    g = [xs, ys]  (xs, 1)  {k: xs}  [xs for ...]              a display or comprehension holding it
    Bag(ys)                      a constructor whose __init__ stores the parameter
    r = ident(xs)  r = get(b)    a function that returns a parameter, a field or an element of one
    grow(g, xs)  b.add(xs)       a function that stores one parameter in another

An approximate flow scan, per function, over a link graph: each such site LINKS two names (the
container and the name that now also holds it). A write through one name (element store, `del`,
`+=`, a mutating method, a call whose summary mutates that parameter, or a write through a name
derived from it: `for row in g`, `r = g[0]`, `b.xs.append`) followed by a mention of the other
one -- in the statements after it, or anywhere in an enclosing loop -- is the refusal. Rebinding a
name (`row = []`) ends its links, so a fresh accumulator per iteration is not a hit. Calls are
summarised from the callee's own scan (which parameters it links, returns or mutates), so a helper
`def grow(g, xs): g.append(xs)` is seen at its call sites. A deliberately approximate scan: it
looks at names, annotations and the module's classes, not at a full type for every expression.

AIL_ALIAS_REFUSE=0 switches the check off; AIL_ALIAS_WIDE=0 keeps only the original `name = name`
and `obj.f = name` sites.
"""
import ast
import copy
import os

_LIST = ('append', 'pop', 'clear', 'extend', 'insert', 'remove', 'sort', 'reverse', 'appendleft',
         'extendleft')
_SET = ('add', 'discard', 'remove', 'pop', 'clear', 'update', 'difference_update',
        'intersection_update', 'symmetric_difference_update')
_DICT = ('pop', 'popitem', 'clear', 'update', 'setdefault')
_MUTATORS = frozenset(_LIST + _SET + _DICT)
# method calls that are evidence the receiver is a container (names a user class may also use,
# like `add` or `pop`, are left out)
_CONT_EVIDENCE = frozenset(('append', 'extend', 'insert', 'sort', 'reverse', 'setdefault', 'discard',
                            'popitem', 'appendleft'))
_CONT_ANN = frozenset(('list', 'dict', 'set', 'bytearray', 'List', 'Dict', 'Set', 'deque', 'defaultdict',
                       'Counter', 'MutableSequence', 'MutableMapping', 'MutableSet'))
_CONT_CALLS = frozenset(('list', 'dict', 'set', 'bytearray', 'sorted', 'defaultdict', 'deque', 'Counter'))
_FRESH_METHODS = frozenset(('copy', 'split', 'rsplit', 'splitlines', 'keys', 'values', 'items'))
_DISPLAYS = (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.ListComp, ast.SetComp, ast.DictComp,
             ast.GeneratorExp)


def _ann_container(a):
    if a is None:
        return False
    if isinstance(a, ast.Subscript):
        a = a.value
    if isinstance(a, ast.Attribute):
        return a.attr in _CONT_ANN
    return isinstance(a, ast.Name) and a.id in _CONT_ANN


def _base(e):
    """The name an access path starts from: `b` for `b.xs`, `g` for `g[0].v`."""
    while True:
        if isinstance(e, ast.Name):
            return e.id
        if isinstance(e, (ast.Attribute, ast.Subscript, ast.Starred)):
            e = e.value
        elif isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute):
            e = e.func.value
        else:
            return None


def _fresh(v, funcs):
    """`v` builds a new container."""
    if isinstance(v, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    if isinstance(v, ast.Call):
        f = v.func
        if isinstance(f, ast.Name):
            if f.id in _CONT_CALLS:
                return True
            callee = funcs.get(f.id)
            return callee is not None and _ann_container(callee.returns)
        if isinstance(f, ast.Attribute) and f.attr in _FRESH_METHODS:
            return True
        return False
    if isinstance(v, ast.BinOp) and isinstance(v.op, (ast.Mult, ast.Add)):
        return _fresh(v.left, funcs) or _fresh(v.right, funcs)
    return False


def _containers(fn, mod, extra=()):
    """Names in `fn` that hold a list/dict/set/bytearray, from annotations, initialisers and uses."""
    cont = set(extra)
    args = fn.args
    for a in args.posonlyargs + args.args + args.kwonlyargs:
        if _ann_container(a.annotation):
            cont.add(a.arg)
    for _ in range(3):
        before = len(cont)
        for n in ast.walk(fn):
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                if _ann_container(n.annotation) or (n.value is not None and _container_value(n.value, cont, mod)):
                    cont.add(n.target.id)
            elif isinstance(n, ast.Assign):
                if _container_value(n.value, cont, mod):
                    for t in n.targets:
                        if isinstance(t, ast.Name):
                            cont.add(t.id)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                if n.func.attr in _CONT_EVIDENCE and isinstance(n.func.value, ast.Name):
                    cont.add(n.func.value.id)
            if isinstance(n, (ast.Assign, ast.AugAssign, ast.Delete)):
                for t in (n.targets if not isinstance(n, ast.AugAssign) else [n.target]):
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                        cont.add(t.value.id)
        if len(cont) == before:
            break
    return cont


def _container_value(v, cont, mod):
    if _fresh(v, mod.funcs):
        return True
    if isinstance(v, ast.Name):
        return v.id in cont
    if isinstance(v, ast.Attribute):
        return v.attr in mod.cf
    if isinstance(v, ast.IfExp):
        return _container_value(v.body, cont, mod) or _container_value(v.orelse, cont, mod)
    return False


class _Summary(object):
    """What a call needs to know about a callee, by parameter position."""

    def __init__(self, names):
        self.names = names
        self.links = set()           # (i, j): the callee holds one parameter inside / as the other
        self.ret = set()             # i: the result may be (or hold, or be read out of) parameter i
        self.mut = set()             # i: the callee may write through parameter i


class _Mod(object):
    def __init__(self, fns, classdefs):
        self.funcs = {f.name: f for f in fns}
        self.classes = {c.name: c for c in classdefs}
        self.methods = {}                # method name -> [mangled function names]
        self.inits = {}
        self.cf = set()                  # field names that hold a container
        self.sum = {}
        for c in classdefs:
            for m in c.body:
                if isinstance(m, ast.FunctionDef):
                    if m.name == '__init__':
                        self.inits[c.name] = m
                    else:
                        self.methods.setdefault(m.name, []).append('%s__%s' % (c.name, m.name))
        self._fields(classdefs)
        self._summaries()

    def _fields(self, classdefs):
        for _ in range(2):
            for c in classdefs:
                if c.name.startswith('_AilDDL'):
                    continue
                for m in c.body:
                    if isinstance(m, ast.AnnAssign) and isinstance(m.target, ast.Name) and _ann_container(m.annotation):
                        self.cf.add(m.target.id)
                    if not isinstance(m, ast.FunctionDef):
                        continue
                    cont = _containers(m, self)
                    for n in ast.walk(m):
                        value, target, ann = None, None, None
                        if isinstance(n, ast.Assign) and len(n.targets) == 1:
                            target, value = n.targets[0], n.value
                        elif isinstance(n, ast.AnnAssign):
                            target, value, ann = n.target, n.value, n.annotation
                        if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                                and target.value.id == 'self'):
                            if _ann_container(ann) or (value is not None and _container_value(value, cont, self)):
                                self.cf.add(target.attr)

    def _summaries(self):
        jobs = [(name, f) for name, f in self.funcs.items()]
        jobs += [('C:' + name, f) for name, f in self.inits.items()]
        for _ in range(3):
            changed = False
            for key, f in jobs:
                new = self._summarise(f)
                old = self.sum.get(key)
                if old is None or (old.links, old.ret, old.mut) != (new.links, new.ret, new.mut):
                    self.sum[key] = new
                    changed = True
            if not changed:
                break

    def _summarise(self, f):
        a = f.args
        names = [x.arg for x in a.posonlyargs + a.args]
        cons = _SumCons()
        walk = _Walk(self, f, _containers(f, self), cons)
        walk.block(f.body)
        s = _Summary(names)
        roots = [cons.find(n) for n in names]
        written = {cons.find(w) for w in cons.writes}
        returned = {cons.find(r) for r in walk.ret_refs}
        for i, ri in enumerate(roots):
            if ri in written:
                s.mut.add(i)
            if ri in returned:
                s.ret.add(i)
            for j in range(i + 1, len(names)):
                if roots[j] == ri:
                    s.links.add((i, j))
        return s


class _Hit(Exception):
    def __init__(self, info):
        Exception.__init__(self)
        self.info = info


class _SumCons(object):
    """Flow-insensitive consumer: union-find over linked names, plus the set of written names."""

    def __init__(self):
        self.parent = {}
        self.writes = set()

    def find(self, n):
        self.parent.setdefault(n, n)
        while self.parent[n] != n:
            self.parent[n] = self.parent[self.parent[n]]
            n = self.parent[n]
        return n

    def link(self, a, b, info):
        self.parent[self.find(a)] = self.find(b)

    def write(self, n):
        self.writes.add(n)

    def mention(self, n):
        pass

    def kill(self, n):
        pass

    def snap(self):
        return None

    def restore(self, s):
        pass

    def merge(self, states):
        return None


class _CheckCons(object):
    """Ordered consumer: the live links, each with the names written since it was made."""

    def __init__(self):
        self.st = {}

    def link(self, a, b, info):
        key = frozenset((a, b))
        if key not in self.st:
            self.st[key] = (frozenset(), info)

    def write(self, n):
        for key, (dirty, info) in list(self.st.items()):
            if n in key and n not in dirty:
                self.st[key] = (dirty | {n}, info)

    def mention(self, n):
        for key, (dirty, info) in self.st.items():
            if dirty and n in key:
                other = [x for x in key if x != n]
                if other and other[0] in dirty:
                    raise _Hit(info)

    def kill(self, n):
        for key in [k for k in self.st if n in k]:
            del self.st[key]

    def snap(self):
        return dict(self.st)

    def restore(self, s):
        self.st = dict(s)

    def merge(self, states):
        out = {}
        for s in states:
            for key, (dirty, info) in s.items():
                if key in out:
                    out[key] = (out[key][0] | dirty, out[key][1])
                else:
                    out[key] = (dirty, info)
        return out


class _Strip(ast.NodeTransformer):
    """Spell the nested-list row wrappers (`_AilRow_int(xs)`) the way the user wrote them."""

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id.startswith('_AilRow_') and len(node.args) == 1:
            return node.args[0]
        if isinstance(node.func, ast.Name) and node.func.id.startswith('_AilT_'):
            return ast.Tuple(elts=list(node.args), ctx=ast.Load())
        return node


def _text(st):
    try:
        node = copy.deepcopy(st)
        if isinstance(node, ast.stmt):
            for field in ('body', 'orelse', 'finalbody', 'handlers'):
                if hasattr(node, field):
                    setattr(node, field, [])
        text = ast.unparse(_Strip().visit(node)).strip().splitlines()[0]
    except Exception:
        return '...'
    return text if len(text) <= 70 else text[:67] + '...'


def _wide():
    return os.environ.get('AIL_ALIAS_WIDE', '1') != '0'


class _Walk(object):
    def __init__(self, mod, fn, cont, cons):
        self.mod, self.fn, self.cont, self.cons = mod, fn, cont, cons
        self.loops = []
        self.ret_refs = set()
        self.ret_container = _ann_container(fn.returns)
        self.wide = _wide()
        self.only = None
        self.derived = self._derived(fn)

    # -- names derived from another (`for row in g`, `r = g[0]`, `zs = b.xs`) -------------------
    def _derived(self, fn):
        derived = {}

        def source(e):
            for _ in range(4):
                if (isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute)
                        and e.func.attr in ('items', 'values', 'keys', 'copy')):
                    e = e.func.value
                elif (isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.args
                        and e.func.id in ('enumerate', 'reversed', 'zip', 'sorted', 'list')):
                    e = e.args[0]
                else:
                    break
            if isinstance(e, (ast.Subscript, ast.Attribute, ast.Name)):
                return _base(e)
            return None

        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and isinstance(n.value, (ast.Subscript, ast.Attribute)):
                src = _base(n.value)
                for t in n.targets:
                    if isinstance(t, ast.Name) and src and src != t.id and not (
                            isinstance(n.value, ast.Subscript) and isinstance(n.value.slice, ast.Slice)):
                        derived.setdefault(t.id, src)
            elif isinstance(n, (ast.For, ast.AsyncFor)):
                src = source(n.iter)
                if src:
                    for t in ast.walk(n.target):
                        if isinstance(t, ast.Name) and t.id != src:
                            derived.setdefault(t.id, src)
        return derived

    def roots(self, n):
        chain, seen = [n], {n}
        while chain[-1] in self.derived and self.derived[chain[-1]] not in seen:
            seen.add(self.derived[chain[-1]])
            chain.append(self.derived[chain[-1]])
        return chain

    def mention(self, n):
        for r in self.roots(n):
            self.cons.mention(r)

    def write(self, n):
        for r in self.roots(n):
            self.cons.write(r)

    def kill(self, n):
        self.cons.kill(n)

    def link(self, a, b, node, kind='site'):
        if self.only is not None and kind not in self.only:
            return
        if a != b and not a.startswith(('_ail', '_Ail')) and not b.startswith(('_ail', '_Ail')) \
                and (self.wide or kind in ('name', 'field_name')):
            self.cons.link(a, b, (getattr(node, 'lineno', 0), _text(node), a, b, kind))

    # -- what a value holds ---------------------------------------------------------------------
    def refs(self, e):
        """Container names whose object `e` evaluates to, holds, or reads out of."""
        if isinstance(e, ast.Name):
            return {e.id} if e.id in self.cont else set()
        if isinstance(e, ast.Attribute):
            b = _base(e)
            return {b} if b and e.attr in self.mod.cf else set()
        if isinstance(e, ast.IfExp):
            return self.refs(e.body) | self.refs(e.orelse)
        if isinstance(e, ast.BoolOp):
            return set().union(*[self.refs(v) for v in e.values])
        if isinstance(e, (ast.NamedExpr, ast.Starred)):
            return self.refs(e.value)
        if isinstance(e, (ast.List, ast.Tuple, ast.Set)):
            return set().union(*[self.refs(v) for v in e.elts]) if e.elts else set()
        if isinstance(e, ast.Dict):
            return set().union(*[self.refs(v) for v in e.values if v is not None]) if e.values else set()
        if isinstance(e, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            return self.refs(e.elt)
        if isinstance(e, ast.DictComp):
            return self.refs(e.value)
        if isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Add, ast.Mult)):
            out = set()
            for side in (e.left, e.right):
                if isinstance(side, _DISPLAYS):
                    out |= self.refs(side)
            return out
        if isinstance(e, ast.Call):
            return self.call_refs(e)
        return set()

    def argexprs(self, key, call, receiver=None):
        """`call`'s argument expressions by the callee's parameter position (None: unknown)."""
        s = self.mod.sum.get(key)
        if s is None:
            return None, None
        slots = [None] * len(s.names)
        pos = ([receiver] if receiver is not None else ([None] if key.startswith('C:') else [])) + list(call.args)
        for i, a in enumerate(pos):
            if i < len(slots) and not isinstance(a, ast.Starred):
                slots[i] = a
        for k in call.keywords:
            if k.arg in s.names:
                slots[s.names.index(k.arg)] = k.value
        return s, slots

    def call_targets(self, c):
        """[(summary key, receiver expr or None)] for a call to something defined in the module."""
        f = c.func
        if isinstance(f, ast.Name):
            if f.id in self.mod.inits and f.id in self.mod.classes:
                return [('C:' + f.id, None)]
            if f.id in self.mod.funcs:
                return [(f.id, None)]
        elif isinstance(f, ast.Attribute) and f.attr in self.mod.methods:
            rb = _base(f.value)
            if f.attr in _MUTATORS and rb in self.cont:
                return []                       # a built-in container method, not the user's
            return [(k, f.value) for k in self.mod.methods[f.attr]]
        return []

    def call_refs(self, c):
        out = set()
        for key, recv in self.call_targets(c):
            s, slots = self.argexprs(key, c, recv)
            if s is None:
                continue
            if key.startswith('C:'):
                for (i, j) in s.links:
                    if i == 0 and slots[j] is not None:
                        out |= self.refs(slots[j])
            else:
                for i in s.ret:
                    if slots[i] is not None:
                        out |= self.argnames(slots[i])
        return out

    def _calls_user_function(self, value):
        return isinstance(value, ast.Call) and any(not k.startswith('C:') for k, _ in self.call_targets(value))

    def argnames(self, e):
        out = set()
        if isinstance(e, (ast.Name, ast.Attribute, ast.Subscript)):
            b = _base(e)
            if b:
                out.add(b)
        return out | self.refs(e)

    # -- effects ----------------------------------------------------------------------------------
    def call(self, c, st):
        f = c.func
        if isinstance(f, ast.Attribute) and f.attr in _MUTATORS:
            rb = _base(f.value)
            targets = self.call_targets(c)
            if rb is not None and (rb in self.cont or not targets):
                self.write(rb)
                if f.attr in ('append', 'appendleft'):
                    stored = c.args[:1]
                elif f.attr in ('insert', 'setdefault'):
                    stored = c.args[1:2]
                elif f.attr in ('extend', 'extendleft', 'update'):
                    stored = [a for a in c.args if isinstance(a, _DISPLAYS)]
                else:
                    stored = []
                for v in stored:
                    for r in self.refs(v):
                        self.link(r, rb, st)
                return
        for key, recv in self.call_targets(c):
            s, slots = self.argexprs(key, c, recv)
            if s is None:
                continue
            for i in s.mut:
                if slots[i] is not None:
                    for n in self.argnames(slots[i]):
                        self.write(n)
            for (i, j) in s.links:
                if slots[i] is not None and slots[j] is not None:
                    for a in self.argnames(slots[i]):
                        for b in self.argnames(slots[j]):
                            self.link(a, b, st)

    def effects(self, nodes, st):
        for node in nodes:
            for n in ast.walk(node):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    self.mention(n.id)
        for node in nodes:
            for n in ast.walk(node):
                if isinstance(n, ast.Call):
                    self.call(n, st)

    def target(self, t, value, rs, st):
        if isinstance(t, ast.Name):
            self.kill(t.id)
            kind = ('name' if isinstance(value, ast.Name) else 'callret' if self._calls_user_function(value)
                    else 'site')
            for r in rs:
                self.link(t.id, r, st, kind)
        elif isinstance(t, (ast.Tuple, ast.List)):
            if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(t.elts):
                for tt, vv in zip(t.elts, value.elts):
                    self.target(tt, vv, self.refs(vv), st)
            else:
                for tt in t.elts:
                    self.target(tt, None, rs, st)
        elif isinstance(t, ast.Starred):
            self.target(t.value, None, rs, st)
        elif isinstance(t, ast.Subscript):
            b = _base(t)
            if b:
                self.write(b)
                for r in rs:
                    self.link(r, b, st)
        elif isinstance(t, ast.Attribute):
            b = _base(t)
            if b:
                for r in rs:
                    self.link(r, b, st, 'field_name' if isinstance(value, ast.Name) else 'site')

    def simple(self, st):
        if isinstance(st, (ast.Assign, ast.AnnAssign)):
            value = st.value
            targets = st.targets if isinstance(st, ast.Assign) else [st.target]
            self.effects([n for n in [value] + [t for t in targets if not isinstance(t, ast.Name)]
                          if n is not None], st)
            if value is not None:
                rs = self.refs(value)
                for t in targets:
                    self.target(t, value, rs, st)
            return False
        if isinstance(st, ast.AugAssign):
            t = st.target
            self.effects([st.value] if isinstance(t, ast.Name) else [st.value, t], st)
            b = _base(t)
            if isinstance(t, ast.Name):
                self.mention(t.id)
            if b and ((isinstance(t, ast.Name) and t.id in self.cont) or isinstance(t, ast.Subscript)
                      or (isinstance(t, ast.Attribute) and t.attr in self.mod.cf)):
                self.write(b)
                if isinstance(st.value, _DISPLAYS):
                    for r in self.refs(st.value):
                        self.link(r, b, st)
            return False
        if isinstance(st, ast.Delete):
            self.effects([t for t in st.targets if not isinstance(t, ast.Name)], st)
            for t in st.targets:
                if isinstance(t, ast.Name):
                    self.kill(t.id)
                elif isinstance(t, ast.Subscript) and _base(t):
                    self.write(_base(t))
            return False
        if isinstance(st, ast.Return):
            if st.value is not None:
                self.effects([st.value], st)
                self.ret_refs |= self.refs(st.value)
                if self.ret_container and isinstance(st.value, ast.Subscript) \
                        and not isinstance(st.value.slice, ast.Slice) and _base(st.value):
                    self.ret_refs.add(_base(st.value))
            return True
        if isinstance(st, ast.Raise):
            self.effects([n for n in (st.exc, st.cause) if n is not None], st)
            return True
        if isinstance(st, (ast.Pass, ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom,
                           ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False
        self.effects([st], st)
        return False

    # -- control flow -----------------------------------------------------------------------------
    def block(self, stmts):
        for st in stmts:
            if self.stmt(st):
                return True
        return False

    def stmt(self, st):
        cons = self.cons
        if isinstance(st, ast.If):
            self.effects([st.test], st)
            s0 = cons.snap()
            t1 = self.block(st.body)
            s1 = cons.snap()
            cons.restore(s0)
            t2 = self.block(st.orelse)
            s2 = cons.snap()
            live = [s for s, t in ((s1, t1), (s2, t2)) if not t]
            if not live:
                return True
            cons.restore(cons.merge(live))
            return False
        if isinstance(st, (ast.For, ast.AsyncFor, ast.While)):
            return self.loop(st)
        if isinstance(st, ast.Break):
            if self.loops:
                self.loops[-1][0].append(cons.snap())
            return True
        if isinstance(st, ast.Continue):
            if self.loops:
                self.loops[-1][1].append(cons.snap())
            return True
        if isinstance(st, ast.Try) or type(st).__name__ == 'TryStar':
            s0 = cons.snap()
            t_body = self.block(st.body)
            s_body = cons.snap()
            ends = [] if t_body else [s_body]
            if st.orelse and not t_body:
                cons.restore(s_body)
                ends = [] if self.block(st.orelse) else [cons.snap()]
            for h in st.handlers:
                cons.restore(cons.merge([s0, s_body]))
                if h.name:
                    self.kill(h.name)
                if not self.block(h.body):
                    ends.append(cons.snap())
            if not ends:
                if st.finalbody:
                    cons.restore(cons.merge([s0, s_body]))
                    self.block(st.finalbody)
                return True
            cons.restore(cons.merge(ends))
            return self.block(st.finalbody) if st.finalbody else False
        if isinstance(st, (ast.With, ast.AsyncWith)):
            self.effects([i.context_expr for i in st.items], st)
            for i in st.items:
                if i.optional_vars is not None:
                    for n in ast.walk(i.optional_vars):
                        if isinstance(n, ast.Name):
                            self.kill(n.id)
            return self.block(st.body)
        if type(st).__name__ == 'Match':
            self.effects([st.subject], st)
            s0 = cons.snap()
            ends = []
            for case in st.cases:
                cons.restore(s0)
                if not self.block(case.body):
                    ends.append(cons.snap())
            cons.restore(cons.merge(ends + [s0]))
            return False
        return self.simple(st)

    def loop(self, st):
        cons = self.cons
        is_for = not isinstance(st, ast.While)
        if is_for:
            self.effects([st.iter], st)
        entry = cons.snap()
        starts = entry
        exits, breaks = [entry], []
        for _ in range(2):
            cons.restore(starts)
            self.loops.append(([], []))
            if is_for:
                for n in ast.walk(st.target):
                    if isinstance(n, ast.Name):
                        self.kill(n.id)
            else:
                self.effects([st.test], st)
            term = self.block(st.body)
            brk, cont = self.loops.pop()
            breaks += brk
            ends = ([] if term else [cons.snap()]) + cont
            exits += ends
            starts = cons.merge([entry] + ends)
        cons.restore(cons.merge(exits + breaks))
        if st.orelse:
            self.block(st.orelse)
        return False


_MODULE = {'fns': (), 'classes': (), 'mod': None}


def set_module(fns, classdefs):
    """The whole program's functions (methods already under their mangled names) and classes."""
    _MODULE['fns'], _MODULE['classes'], _MODULE['mod'] = fns, classdefs, None


def _module():
    if _MODULE['mod'] is None:
        _MODULE['mod'] = _Mod(list(_MODULE['fns']), list(_MODULE['classes']))
        if os.environ.get('AIL_ALIAS_DEBUG'):
            import sys
            m = _MODULE['mod']
            print('alias: fields', sorted(m.cf), 'classes', sorted(m.classes), file=sys.stderr)
            for k, s in sorted(m.sum.items()):
                print('alias: summary', k, s.names, 'links', sorted(s.links), 'ret', sorted(s.ret), 'mut',
                      sorted(s.mut), file=sys.stderr)
    return _MODULE['mod']


def find(P, fn, ctx, only=None):
    """(line, text, a, b, kind) of the first hit in `fn`, or None."""
    kinds = getattr(ctx, 'types', {}) or {}
    containers = {P.LIST, P.FLIST, P.SLIST, P.BLIST, P.OLIST, P.HLIST, P.SET, P.DICT,
                  P.BYTEARRAY, *P.MAPS}
    mod = _module()
    cont = _containers(fn, mod, [n for n, k in kinds.items() if k in containers])
    walk = _Walk(mod, fn, cont, _CheckCons())
    walk.only = only
    try:
        walk.block(fn.body)
    except _Hit as hit:
        return hit.info
    return None


def _active():
    return os.environ.get('AIL_SURFACE') == 'python' and os.environ.get('AIL_ALIAS_REFUSE') != '0'


def refuse_instead(P, fn, refusal):
    """The legacy emitter refused `fn` for another reason. If `fn` also has an aliasing site, that is
    the reason worth naming (the other refusal can be a symptom, like a str key in a dict that was
    never annotated `dict[str, ...]`, which hides what CPython would have done differently)."""
    if not _active() or 'used where a number is needed' not in str(refusal):
        return
    try:
        hit = find(P, fn, None)
    except Exception:
        return
    if hit is not None:
        _refuse(P, hit)


def check_ir(P, fn, ctx):
    """The IR took `fn` (and shares what its own scan understands). A name bound to the result of a
    call to a function that returns one of its parameters, fields or elements is not among those
    shapes, so that one site is still refused here."""
    if not _active():
        return
    hit = find(P, fn, ctx, only=('callret',))
    if hit is not None:
        _refuse(P, hit)


def check(P, fn, ctx):
    """Raise P.Unsupported for the first aliasing site of a def-syntax function."""
    if not _active():
        return
    hit = find(P, fn, ctx)
    if hit is not None:
        _refuse(P, hit)


def _refuse(P, hit):
    line, text, a, b, kind = hit
    if kind == 'name':
        dst, src = a, b
        raise P.Unsupported(
            'line %d: `%s = %s` makes a second name for the same container, and one of the two is '
            'written while the other is read afterwards. CPython shares the object there (a write '
            'through one name shows in the other); this compiler would copy and print something '
            'else, so it refuses rather than differ. If a copy was meant, write `%s = %s.copy()` '
            '(or list(%s) / dict(%s) / set(%s) / bytearray(%s)); if sharing was meant, '
            'keep a single name or pass the container to a function'
            % (line, dst, src, dst, src, src, src, src, src))
    raise P.Unsupported(
        'line %d: `%s` makes a second reference to the same container (`%s` and `%s` are one '
        'list/dict/set, or one holds the other), and one of the two is written while the other is '
        'read afterwards. CPython shares the object there (a write through one shows in the other); '
        'this compiler would copy and print something else, so it refuses rather than differ. If a '
        'copy was meant, store `%s.copy()` (or list(%s) / dict(%s) / set(%s) / bytearray(%s)) '
        'instead; if sharing was meant, keep a single name or pass the container to a function'
        % (line, text, a, b, a, a, a, a, a))
