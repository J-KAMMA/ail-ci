# -*- coding: utf-8 -*-
"""numidentity.py -- `is` / `is not` on numbers (DIFFERENCES C114, C115).

CPython's `is` on two numbers answers by where each was made: the ints -5..256 are shared, equal constants of one code object are
merged (`t = 2.5; t is 2.5` is True), and two equal ints computed at run time are two objects (`a = n + 1000; b = n + 1000;
a is b` is False). Here an int is a value (a C integer in the typed path, a tagged value in the general one) and a float literal
is a box of its own, so the answers can differ and no cheap rule reproduces them. The compiler therefore refuses, by name:

  C115  `is` / `is not` with a numeric literal operand (not an int literal of -5..256, which CPython caches: `x is 0`,
        `x is not 256`, `n is -5` answer `==` for an int and False for a bool or anything else, and are lowered so), or an operand that is only constants (`2.5`, `-1`, `1.5 + 1`, a name that
        is only ever bound to such a value, an item of a list / tuple written out with number literals): CPython merges equal
        constants of a code object and warns `SyntaxWarning: "is" with a literal`.
  C114  `is` / `is not` between two operands where one is statically an int (or a number that may be an int): `len(x)`, `int(s)`, `n + 1`
        with a number, a local only ever bound to such values, a parameter annotated `int`.

Not refused: `is` of an object with itself or an expression built from it (`(x or "o") is not x`, `x is x`: the same object);
`is` against None, True, False, a str or bytes constant (one answer in CPython and here); two floats made by
arithmetic or `float(...)` (each is a box of its own, as in CPython: `a = n / 2; b = n / 2; a is b` is False on both); anything
whose type this scan cannot see (`a is b` of two parameters, attributes, items). For the last group the general-path runtime stops
with a message naming C114 when both operands are ints of the same value outside -5..256 (`ail_is`).
The scan is syntactic and per scope, so it can miss a number reached through a call, an attribute or an unannotated parameter
(DIFFERENCES C115-silent2-1), and it can refuse an `is` that would have been right.
"""
import ast

_ARITH = (ast.Add, ast.Sub, ast.Div, ast.FloorDiv, ast.Pow, ast.LShift, ast.RShift, ast.BitAnd, ast.BitOr, ast.BitXor)
_BOTH = (ast.Mult, ast.Mod)
_INT_CALLS = ('len', 'ord', 'hash', 'id')
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_COMPS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_MUTATORS = frozenset(('append', 'extend', 'insert', 'remove', 'pop', 'clear', 'sort', 'reverse', '__setitem__'))


_BOTTOM = object()


def _same(a, b):
    if a is None or b is None or a is _BOTTOM or b is _BOTTOM:
        return a is b
    return (a.kind, a.lit) == (b.kind, b.lit)


class _K(object):
    """kind of an expression: 'int', 'float' or 'num' (an int or a float), and `lit` (made of constants only)"""
    __slots__ = ('kind', 'lit')

    def __init__(self, kind, lit=False):
        self.kind, self.lit = kind, lit


def _join(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return _K(a.kind if a.kind == b.kind else 'num', a.lit and b.lit)


def _own_nodes(scope):
    """the nodes of one scope, not those of a nested function / class / lambda (a comprehension is walked: its targets are noted)"""
    body = scope.body if not isinstance(scope, ast.Lambda) else [scope.body]
    todo = list(body) if isinstance(body, list) else [body]
    while todo:
        n = todo.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if isinstance(c, _SCOPES):
                # decorators and defaults belong to the outer scope, the name of a def is a binding
                if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    yield c
                continue
            todo.append(c)


class _Scope(object):
    def __init__(self, node, module):
        self.node, self.module = node, module
        self.bindings = {}          # name -> list of expressions (or None = something this scan cannot type)
        self.declared = set()       # global / nonlocal names
        self.displays = {}          # name -> per binding, which items of its display are number literals; False otherwise
        self.kinds = {}
        self._scan()

    def _bind(self, name, value):
        self.bindings.setdefault(name, []).append(value)
        # per binding, which items of the display are number literals: `h = [0, [1, 2]]` makes only h[0] a number
        flags = tuple(isinstance(e, ast.Constant) and isinstance(e.value, (int, float, complex))
                      and not isinstance(e.value, bool) for e in value.elts) \
            if isinstance(value, (ast.List, ast.Tuple)) and any(isinstance(e, ast.Constant) for e in value.elts) else None
        prior = self.displays.get(name, [])
        self.displays[name] = prior + [flags] if prior is not False and flags is not None else False

    def _targets(self, target, value):
        if isinstance(target, ast.Name):
            self._bind(target.id, value)
        elif isinstance(target, (ast.Tuple, ast.List, ast.Starred)):
            for e in ast.walk(target):
                if isinstance(e, ast.Name) and isinstance(e.ctx, ast.Store):
                    self._bind(e.id, None)

    def _scan(self):
        node = self.node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = node.args
            for p in a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]:
                ann = getattr(p, 'annotation', None)
                if isinstance(ann, ast.Name) and ann.id in ('int', 'float'):
                    self._bind(p.arg, ast.Call(func=ast.Name(id=ann.id, ctx=ast.Load()), args=[], keywords=[]))
                else:
                    self._bind(p.arg, None)
        for n in _own_nodes(node):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    self._targets(t, n.value)
            elif isinstance(n, ast.AnnAssign):
                if isinstance(n.target, ast.Name):
                    self._bind(n.target.id, n.value)
            elif isinstance(n, ast.AugAssign):
                if isinstance(n.target, ast.Name):
                    aug = ast.BinOp(left=ast.Name(id=n.target.id, ctx=ast.Load()), op=n.op, right=n.value)
                    aug._aug = True
                    self._bind(n.target.id, aug)
            elif isinstance(n, (ast.For, ast.AsyncFor)):
                it = n.iter
                rng = (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range'
                       and isinstance(n.target, ast.Name))
                if rng:
                    self._bind(n.target.id, ast.Call(func=ast.Name(id='int', ctx=ast.Load()), args=[], keywords=[]))
                else:
                    self._targets(n.target, None)
            elif isinstance(n, ast.comprehension):
                self._targets(n.target, None)
            elif isinstance(n, ast.NamedExpr):
                self._targets(n.target, None)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self._bind(n.name, None)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for al in n.names:
                    self._bind((al.asname or al.name).split('.')[0], None)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                self._bind(n.name, None)
            elif isinstance(n, (ast.With, ast.AsyncWith)):
                for it in n.items:
                    if it.optional_vars is not None:
                        self._targets(it.optional_vars, None)
            elif isinstance(n, (ast.Global, ast.Nonlocal)):
                self.declared.update(n.names)
            elif isinstance(n, ast.Delete):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        self._bind(t.id, None)
            elif isinstance(n, ast.Subscript) and isinstance(n.ctx, (ast.Store, ast.Del)) and isinstance(n.value, ast.Name):
                self.displays[n.value.id] = False
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                  and n.func.attr in _MUTATORS):
                self.displays[n.func.value.id] = False
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Subscript):
                pass
        for name in list(self.declared):
            self.bindings.setdefault(name, []).append(None)


class _Scan(object):
    def __init__(self, tree):
        self.tree = tree
        self.module = _Scope(tree, True)
        self.scopes = {id(tree): self.module}
        self.shadowed = {name for name in self.module.bindings if name in _INT_CALLS + ('int', 'float')}
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                self.scopes[id(n)] = _Scope(n, False)
        # a name another scope declares global is not a constant of the module
        for s in self.scopes.values():
            if not s.module:
                for name in s.declared:
                    self.module.bindings.setdefault(name, []).append(None)
        for s in self.scopes.values():
            self._solve(s)

    def _solve(self, s):
        for name, values in s.bindings.items():
            s.kinds[name] = None if any(v is None for v in values) else _BOTTOM
        for _ in range(10):
            changed = False
            for name, values in s.bindings.items():
                if s.kinds[name] is None:
                    continue
                acc, ok = None, True
                for v in values:
                    k = self.kind(v, s, name)
                    if k is False:          # depends on a name that is not solved yet
                        continue
                    if k is None:
                        ok = False
                        break
                    acc = _join(acc, k)
                new = None if not ok else (acc if acc is not None else _BOTTOM)
                if not _same(new, s.kinds[name]):
                    s.kinds[name] = new
                    changed = True
            if not changed:
                break
        for name, k in list(s.kinds.items()):
            if k is _BOTTOM:
                s.kinds[name] = None

    def name_kind(self, name, s):
        if name in s.bindings:
            if name in s.declared:
                return None
            k = s.kinds.get(name)
            return False if k is _BOTTOM else k
        if s.module:
            return None
        # not bound here: a module name (a closure variable of an enclosing function is not known)
        if name in self.module.bindings:
            k = self.module.kinds.get(name)
            return None if k is _BOTTOM else k
        return None

    def kind(self, e, s, own=None):
        """a _K, None (not a number this scan knows) or False (depends on a name not solved yet)"""
        if isinstance(e, ast.Constant):
            if isinstance(e.value, bool) or not isinstance(e.value, (int, float, complex)):
                return None
            return _K('int' if isinstance(e.value, int) else 'float' if isinstance(e.value, float) else 'num', True)
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, (ast.USub, ast.UAdd, ast.Invert)):
            return self.kind(e.operand, s, own)
        if isinstance(e, ast.BinOp):
            a, b = self.kind(e.left, s, own), self.kind(e.right, s, own)
            if a is False or b is False:
                return False
            if isinstance(e.op, _BOTH):
                if a is None or b is None:
                    return None
            elif isinstance(e.op, _ARITH):
                if a is None and b is None:
                    return None
            else:
                return None
            kinds = [x.kind for x in (a, b) if x is not None]
            if isinstance(e.op, ast.Div):
                kind = 'float' if all(x in ('int', 'float') for x in kinds) and len(kinds) == 2 else 'num'
            elif len(kinds) == 2 and kinds[0] == kinds[1] and not isinstance(e.op, ast.Pow):
                kind = kinds[0]
            elif 'float' in kinds and isinstance(e.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)):
                kind = 'float'          # int + float, float + unknown number: a float
            else:
                kind = 'num'
            return _K(kind, a is not None and b is not None and a.lit and b.lit and not getattr(e, '_aug', False))
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and not e.keywords:
            f = e.func.id
            if f in self.shadowed or f in self.module.bindings and f not in ('int', 'float'):
                return None
            if f in _INT_CALLS or f == 'int':
                return _K('int')
            if f == 'float':
                return _K('float')
            return None
        if isinstance(e, ast.Name):
            return self.name_kind(e.id, s)
        if (isinstance(e, ast.Subscript) and isinstance(e.value, ast.Name) and isinstance(e.slice, ast.Constant)
                and isinstance(e.slice.value, int)):
            sc = s if e.value.id in s.bindings else self.module
            disp, i = sc.displays.get(e.value.id), e.slice.value
            if disp and e.value.id not in sc.declared and (sc is s or not s.module) and all(
                    -len(f) <= i < len(f) and f[i] for f in disp):
                return _K('num', True)
        return None


def small_int(e):
    """the value of an int literal (`5`, `-5`, `+3`) that CPython caches (-5..256), else None. `is` against it is deterministic:
    an int operand is it exactly when it is equal, and anything else (a bool, a float, a str, None) is never it."""
    sign = 1
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, (ast.USub, ast.UAdd)):
        sign = -1 if isinstance(e.op, ast.USub) else 1
        e = e.operand
    if isinstance(e, ast.Constant) and type(e.value) is int and -5 <= sign * e.value <= 256:
        return sign * e.value
    return None


def _derived(e, other):
    """`other` is built from `e` (a name or an item) itself: `x or "o"`, `x and 1`, `x`; then `is` asks whether it is the same object,
    which a value here answers as CPython does (a box for a float, the value for an int)"""
    if not isinstance(e, (ast.Name, ast.Subscript)):
        return False
    want = ast.dump(e)
    return any(isinstance(n, type(e)) and ast.dump(n) == want for n in ast.walk(other))


def _fits(e, k):
    """the other operand of `is` against a cached int literal: anything but a constant float, an int literal outside -5..256 or a
    name / expression only made of such constants (`x is 0` answers `==` for an int and False for the rest, whatever x is)"""
    if isinstance(e, (ast.Constant, ast.UnaryOp)) and k is not None and k.lit:
        return small_int(e) is not None
    return k is None or not (k.lit and k.kind == 'float')


def _exempt(e):
    return isinstance(e, ast.Constant) and (e.value is None or e.value is Ellipsis or isinstance(e.value, (bool, str, bytes)))


def _text_constant(e):
    return isinstance(e, ast.Constant) and isinstance(e.value, (str, bytes))


def _text_refusal(op, line):
    return ('`%s` on two string/bytes constants (line %d, DIFFERENCES C?-job-fuzz90-10231630-1): CPython merges equal '
            'constants of a code object and interns strings, so `"a" is "a"` can be True, while here each string value '
            'has its own address; compare strings with `==`' % ('is not' if isinstance(op, ast.IsNot) else 'is', line))


def find(tree):
    """the first `is` / `is not` comparison of the program that this module refuses: (node, text), or None"""
    scan = None
    owners = {}
    for sc in ast.walk(tree):
        if isinstance(sc, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for n in _own_nodes(sc):
                if isinstance(n, ast.Compare) and any(isinstance(o, (ast.Is, ast.IsNot)) for o in n.ops):
                    owners[id(n)] = (n, sc)
    if not owners:
        return None
    scan = _Scan(tree)
    for n, sc in sorted(owners.values(), key=lambda x: (x[0].lineno, x[0].col_offset)):
        s = scan.scopes[id(sc)]
        sides = [n.left] + list(n.comparators)
        for i, o in enumerate(n.ops):
            if not isinstance(o, (ast.Is, ast.IsNot)):
                continue
            a, b = sides[i], sides[i + 1]
            if _text_constant(a) and _text_constant(b):
                return n, _text_refusal(o, n.lineno)
            if _exempt(a) or _exempt(b):
                continue
            ka, kb = scan.kind(a, s), scan.kind(b, s)
            ka = ka or None         # False (not solved) is not a number this scan knows
            kb = kb or None
            # an int literal of -5..256 against anything that is not itself a constant number: CPython answers `==` for an int
            # and False for everything else, whatever the operand's history (the other operand is lowered that way)
            if _derived(a, b) or _derived(b, a):
                continue            # `(x or "o") is not x`: the same object (or its stand-in), not two constants that CPython merges
            sa, sb = small_int(a) is not None, small_int(b) is not None
            if (sa and _fits(b, kb)) or (sb and _fits(a, ka)):
                continue
            if (ka is not None and ka.lit) or (kb is not None and kb.lit):
                return n, ('`%s` with a number constant (line %d, DIFFERENCES C115): CPython merges equal constants of a code '
                           'object (`t = 2.5; t is 2.5` is True) and here each literal is a value of its own; compare '
                           'numbers with `==`' % ('is not' if isinstance(o, ast.IsNot) else 'is', n.lineno))
            if (ka is not None and ka.kind != 'float') or (kb is not None and kb.kind != 'float'):
                return n, ('`%s` between ints (line %d, DIFFERENCES C114): CPython shares the ints -5..256 and makes two '
                           'objects of two equal ints computed at run time, here an int is a value; compare numbers with '
                           '`==`' % ('is not' if isinstance(o, ast.IsNot) else 'is', n.lineno))
    return None


def refusal(source):
    """the refusal text for a program (Python source) that has such a comparison, or None"""
    if ' is ' not in source:
        return None
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    got = find(tree)
    return None if got is None else got[1]
