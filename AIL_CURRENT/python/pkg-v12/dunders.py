"""Special methods, class attributes and @staticmethod / @classmethod / @property on the typed path.

Run first on the parsed module (pyfunc `_to_c_once`), before any other pass looks at it. A program whose
classes use none of these is left untouched, so its C stays byte-identical. Otherwise every implicit use
of a special method whose operand is statically an instance of a class that defines it becomes the
explicit method call CPython 3.12 makes, and every later pass (signatures, aliasing, the C emitter, the IR)
sees ordinary method calls:

* `a + b` -> `a.__add__(b)` (and the other binary operators, `__r*__` when the left operand is a number or
  str, `x += y` -> `x = x.__iadd__(y)` or `x = x.__add__(y)`), `-a` -> `a.__neg__()`, `abs(a)` -> `a.__abs__()`;
* `a == b` -> `a.__eq__(b)`, `a != b` -> `a.__ne__(b)` or `not a.__eq__(b)`, `a < b` -> `a.__lt__(b)` or the
  reflected `b.__gt__(a)`, with `@functools.total_ordering` filling the missing orderings exactly as
  functools does; `sorted` / `.sort()` / `min` / `max` of a list of instances use `<` (or `>` for max);
* `str(x)`, `print(x)`, f-strings, `%s` / `%r` and `str.format` call `__str__` (falling back to `__repr__`)
  or `__repr__`; a list or tuple of instances prints with each element's `__repr__`;
* `len(x)` -> `x.__len__()` (checked `>= 0` as CPython does), truth tests -> `__bool__` or `__len__() != 0`,
  `k in x` -> `x.__contains__(k)`, `x[k]` / `x[k] = v` -> `__getitem__` / `__setitem__`;
* `for v in x` over `__iter__`: `return iter(E)` / `yield from E` / `for e in E: yield e` iterate E itself;
  a generator body is inlined into the loop (break/continue/else kept), or run into a list for an eager
  consumer (`list(x)`, `sum(x)`, `print(*x)`, ...);
* `with x as y:` -> `__enter__`, a try that hands the exception's class to `__exit__` (as a code) and
  re-raises unless `__exit__` returns true, and `__exit__(None, None, None)` on every other way out;
* a class attribute becomes the module variable `C__name` (read as `C.name`, `self.name`, `cls.name`);
  `@staticmethod` / `@classmethod` methods become the functions `C__static__m` / `C__classmethod__m`
  (`cls(...)` builds a `C`); a `@property` getter is a method called on each read;
* a `@dataclass` (ail_syntax's `# ail:dataclass` marker) gets the `__eq__` and `__repr__` it generates when
  a program compares or prints its instances.

A shape this pass does not take is left as written, and the typed path refuses it by name as before
(`comparing class instances`, `print() given a P object`, ...). `ACCEPTED` and `TRUTH` tell pyfunc which
special methods were taken over (`_scan_classes`) and which classes have a truth method (`_truthy`
refuses a truth test this pass could not see through). Classes with a base class, or used as one, are
left alone (inheritance is a separate stage).
"""
import ast
import copy
import re
import os
import string
import sys

_BIN = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul', ast.Div: 'truediv', ast.FloorDiv: 'floordiv',
        ast.Mod: 'mod', ast.Pow: 'pow', ast.MatMult: 'matmul', ast.LShift: 'lshift', ast.RShift: 'rshift',
        ast.BitAnd: 'and', ast.BitOr: 'or', ast.BitXor: 'xor'}
_UN = {ast.USub: '__neg__', ast.UAdd: '__pos__', ast.Invert: '__invert__'}
_CMP = {ast.Eq: '__eq__', ast.NotEq: '__ne__', ast.Lt: '__lt__', ast.LtE: '__le__', ast.Gt: '__gt__',
        ast.GtE: '__ge__'}
_SWAP = {'__lt__': '__gt__', '__gt__': '__lt__', '__le__': '__ge__', '__ge__': '__le__',
         '__eq__': '__eq__', '__ne__': '__ne__'}
ORDER = ('__lt__', '__le__', '__gt__', '__ge__')
METHODS = ({'__str__', '__repr__', '__eq__', '__ne__', '__hash__', '__len__', '__bool__', '__contains__',
            '__getitem__', '__setitem__', '__iter__', '__abs__', '__enter__', '__exit__'}
           | set(ORDER) | set(_UN.values())
           | {'__%s__' % n for n in _BIN.values()} | {'__r%s__' % n for n in _BIN.values()}
           | {'__i%s__' % n for n in _BIN.values()})
_PURE_BUILTINS = {'len', 'str', 'int', 'float', 'abs', 'min', 'max', 'round', 'bool', 'ord', 'chr', 'sum'}
_PRIMS = ('int', 'float', 'str', 'bool')
PURE_CALLS = set()   # this compile's classes whose construction runs no call (their __init__ only stores fields)

ACCEPTED = {}      # class name -> special method names this pass lowered (pyfunc `_scan_classes`)
TRUTH = set()      # classes whose truth value is __bool__ / __len__ (pyfunc `_truthy`)
ANY_EXCEPTION = 'Exception'               # the handler of a with-statement takes every exception (pyfunc `_try_stmt`)
EXC_CODE = '__ail_exc_code__'             # `__ail_exc_code__()`: the handled exception's code (pyfunc `_expr`)
HINT = {}          # @dataclass markers of a source whose comments pyc._rewrite_script dropped (pyc.to_c)


def is_exc_code(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == EXC_CODE
            and not node.args)


def accepted(cls, method):
    return method in ACCEPTED.get(cls, ())


def reset():
    ACCEPTED.clear()
    TRUTH.clear()


# -- types -------------------------------------------------------------------------------------------
# ('C', name, nullable) an instance; ('K', name) the class object; ('L', t) a list; ('D', k, v) a dict;
# ('T', (t, ...)) a tuple; ('S', t) a set; 'int' 'float' 'str' 'bool' 'none'; None unknown.

def inst(t):
    return isinstance(t, tuple) and t[0] == 'C'


def _unify(types):
    known = [t for t in types if t is not None]
    if not known:
        return None
    nullable = 'none' in known
    known = [t for t in known if t != 'none']
    if not known:
        return 'none'
    first = known[0]
    if all(t == first for t in known):
        out = first
    elif all(inst(t) for t in known) and len({t[1] for t in known}) == 1:
        out = ('C', first[1], any(t[2] for t in known))
    elif all(isinstance(t, tuple) and t[0] == 'L' for t in known):
        elt = _unify([t[1] for t in known])
        if elt is None and any(t[1] is not None for t in known):
            return None
        out = ('L', elt)
    elif all(t in ('int', 'float', 'bool') for t in known):
        out = 'float' if 'float' in known else 'int'
    else:
        return None
    if nullable:
        return ('C', out[1], True) if inst(out) else None
    return out


def _const(value):
    return ast.Constant(value=value)


def _name(id_, store=False, synth=True):
    node = ast.Name(id=id_, ctx=ast.Store() if store else ast.Load())
    if synth:
        node._ail_synth = True
    return node


def _call(func, args=()):
    return ast.Call(func=func, args=list(args), keywords=[])


def _mcall(receiver, method, args=()):
    return _call(ast.Attribute(value=receiver, attr=method, ctx=ast.Load()), args)


def _not(node):
    return ast.UnaryOp(op=ast.Not(), operand=node)


def _pure(node):
    """Evaluating `node` twice, or later than written, cannot be told apart (no call, no side effect)."""
    if isinstance(node, (ast.Name, ast.Constant)):
        return True
    if isinstance(node, ast.Attribute):
        return _pure(node.value)
    if isinstance(node, ast.Subscript):
        return _pure(node.value) and _pure(node.slice)
    if isinstance(node, ast.UnaryOp):
        return _pure(node.operand)
    if isinstance(node, ast.BinOp):
        return _pure(node.left) and _pure(node.right)
    return False


def _calls_only_pure(node, yields=False):
    """No call in `node` but the side-effect-free builtins (and, with `yields`, no yield but a plain one);
    no assignment to anything but a name."""
    for each in ast.walk(node):
        if isinstance(each, ast.Call):
            if not (isinstance(each.func, ast.Name) and (each.func.id in _PURE_BUILTINS or each.func.id in PURE_CALLS)):
                return False
        if isinstance(each, (ast.YieldFrom, ast.NamedExpr, ast.Await, ast.Global, ast.Nonlocal)):
            return False
        if isinstance(each, ast.Yield) and not yields:
            return False
        if isinstance(each, (ast.Attribute, ast.Subscript)) and isinstance(each.ctx, (ast.Store, ast.Del)):
            return False
    return True


def _walk_scope(node):
    """ast.walk without descending into nested functions, lambdas or classes."""
    todo = [node]
    while todo:
        each = todo.pop()
        yield each
        for child in ast.iter_child_nodes(each):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            todo.append(child)


def _locate(nodes, origin):
    for node in nodes if isinstance(nodes, list) else [nodes]:
        for child in ast.walk(node):
            if 'lineno' in getattr(child, '_attributes', ()):
                if not hasattr(child, 'lineno'):
                    ast.copy_location(child, origin)
                if not hasattr(child, 'end_lineno') or child.end_lineno is None:
                    child.end_lineno, child.end_col_offset = getattr(origin, 'end_lineno', None), getattr(origin, 'end_col_offset', None)
    return nodes


def _dataclass_markers(source):
    """{class name: {'noeq': bool, 'nocmp': set, 'hide': set}} for the classes ail_syntax wrote from a
    @dataclass (its `# ail:dataclass` marker comment on the line before `class`)."""
    found = {}
    lines = source.strip().splitlines()
    for i, line in enumerate(lines[:-1]):
        text = line.strip()
        if not text.startswith('# ail:dataclass'):
            continue
        m = re.match(r'\s*class\s+([A-Za-z_]\w*)', lines[i + 1])
        if not m:
            continue
        info = {'noeq': ' noeq' in text, 'norepr': ' norepr' in text, 'nocmp': set(), 'hide': set()}
        for key in ('nocmp', 'hide'):
            hit = re.search(r'\b%s=(\S*)' % key, text)
            if hit:
                info[key] = set(n for n in hit.group(1).split(',') if n)
        found[m.group(1)] = info
    return found


def _ann_text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return ast.parse(node.value, mode='eval').body
        except SyntaxError:
            return None
    return node


class _Model:
    """One class: its methods by kind, its class attributes, and why it is left alone (`bad`)."""

    def __init__(self, node, dataclass):
        self.node, self.name = node, node.name
        self.dataclass = dataclass             # None, or the marker's info
        self.methods, self.statics, self.classmethods, self.props = {}, {}, {}, {}
        self.attrs = {}                        # class attribute -> value node, in order
        self.attr_nodes = []                   # the class-body statements that bind them
        self.deferred = set()                  # literal class attributes left to typedinherit.py
        self.slots = []
        self.total_ordering = False
        self.bad = None
        self.synth = {}                        # dataclass methods built on demand: name -> FunctionDef
        self.want = set()                      # dataclass methods some use needs
        self.fields = []                       # instance fields, in __init__ order
        if node.bases or node.keywords:
            self.bad = 'base class'
        for deco in node.decorator_list:
            text = ast.unparse(deco)
            if text in ('total_ordering', 'functools.total_ordering'):
                self.total_ordering = True
            else:
                self.bad = 'decorator'
        for st in node.body:
            if isinstance(st, ast.FunctionDef):
                decos = [ast.unparse(d) for d in st.decorator_list]
                if not decos:
                    self.methods[st.name] = st
                elif decos == ['staticmethod']:
                    self.statics[st.name] = st
                elif decos == ['classmethod']:
                    self.classmethods[st.name] = st
                elif decos == ['property']:
                    self.props[st.name] = st
                else:
                    self.bad = self.bad or 'method decorator'
            elif (isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name)):
                if st.targets[0].id == '__slots__':
                    self.slots.append(st)
                else:
                    self.attrs[st.targets[0].id] = st.value
                    self.attr_nodes.append(st)
            elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                if st.target.id == '__slots__':
                    self.slots.append(st)
                elif st.value is not None:
                    self.attrs[st.target.id] = st.value
                    self.attr_nodes.append(st)
                else:
                    self.attr_nodes.append(st)     # an annotation only: no attribute at run time
            elif isinstance(st, ast.Pass) or (isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant)):
                continue
            else:
                self.bad = self.bad or 'class body statement'
        init = self.methods.get('__init__')
        if init is not None:
            for each in ast.walk(init):
                targets = (each.targets if isinstance(each, ast.Assign) else
                           [each.target] if isinstance(each, (ast.AnnAssign, ast.AugAssign)) else [])
                for t in targets:
                    if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == 'self'
                            and t.attr not in self.fields):
                        self.fields.append(t.attr)
        self.instance_attrs = set(self.fields)
        for fn in self.methods.values():
            for each in ast.walk(fn):
                if (isinstance(each, ast.Attribute) and isinstance(each.ctx, ast.Store)
                        and isinstance(each.value, ast.Name) and each.value.id == 'self'):
                    self.instance_attrs.add(each.attr)

    def dunders(self):
        return {m for m in self.methods if m in METHODS}

    def defer_constants(self, assigned):
        """The class attributes typedinherit.lower_class_attributes builds (a literal no one assigns, not also
        an instance attribute) stay in the class body for it; this pass takes the others."""
        try:
            import typedinherit
        except ImportError:
            return
        keep = []
        for st in self.attr_nodes:
            got = typedinherit.class_attribute(st)
            if (got is not None and typedinherit.literal_kind(got[1]) is not None and got[0] not in assigned
                    and got[0] not in self.instance_attrs):
                self.deferred.add(got[0])
            else:
                keep.append(st)
        self.attr_nodes = keep

    def interesting(self):
        if self.bad:
            return False
        return bool(self.dunders() or self.statics or self.classmethods or self.props or self.attr_nodes
                    or self.slots or self.total_ordering or self.dataclass is not None)

    def has(self, method):
        if method in self.methods or method in self.synth:
            return True
        if self.dataclass is not None and not self.dataclass['noeq'] and method == '__eq__':
            return True
        if self.dataclass is not None and method == '__repr__' and not self.dataclass['norepr']:
            return True
        return False


# -- the type oracle -----------------------------------------------------------------------------------

class _Typer:
    """Static types for the expressions the rewrite looks at: annotations, constructor calls, method and
    function results (annotated or inferred), fields, list elements, loop variables. Unknown is None; a
    wrong guess only costs a refusal, because the typed path checks every kind again."""

    def __init__(self, tree, models, nullable):
        self.models = models
        self.nullable = nullable
        self.funcs = {f.name: f for f in tree.body if isinstance(f, ast.FunctionDef)}
        self.fret, self.mret = {}, {}
        self.fields = {name: {} for name in models}
        self.attr_types = {name: {} for name in models}
        self.envs = {}
        self.owners = {}           # id(fn) -> (class name or None, kind)
        self.fixed_ret = set()
        for f in self.funcs.values():
            self.owners[id(f)] = (None, 'function')
            t = self.ann(f.returns)
            if t is not None:
                self.fret[f.name] = t
                self.fixed_ret.add(id(f))
        for name, m in models.items():
            for table, kind in ((m.methods, 'method'), (m.props, 'method'), (m.statics, 'static'),
                                (m.classmethods, 'class'), (m.synth, 'method')):
                for mname, fn in table.items():
                    self.owners[id(fn)] = (name, kind)
                    t = self.ann(fn.returns)
                    if t is not None:
                        self.mret[(name, mname)] = t
                        self.fixed_ret.add(id(fn))

    # annotations
    def ann(self, node):
        node = _ann_text(node)
        if node is None:
            return None
        if isinstance(node, ast.Constant) and node.value is None:
            return 'none'
        if isinstance(node, ast.Name):
            n = node.id
            if n.startswith('__ail_checked_') and n.endswith('__'):
                n = n[len('__ail_checked_'):-2]
            if n in self.models:
                return ('C', n, n in self.nullable)
            if n in _PRIMS:
                return n
            if n in ('None', 'void'):
                return 'none'
            if n in ('list', 'List'):
                return ('L', None)
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            a, b = self.ann(node.left), self.ann(node.right)
            if b == 'none' and inst(a):
                return ('C', a[1], True)
            if a == 'none' and inst(b):
                return ('C', b[1], True)
            return None
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            head = node.value.id
            if head.startswith('__ail_checked_'):
                head = head[len('__ail_checked_'):]
            args = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            if head in ('list', 'List', 'Sequence') and len(args) == 1:
                return ('L', self.ann(args[0]))
            if head in ('set', 'Set', 'frozenset') and len(args) == 1:
                return ('S', self.ann(args[0]))
            if head in ('dict', 'Dict') and len(args) == 2:
                return ('D', self.ann(args[0]), self.ann(args[1]))
            if head in ('tuple', 'Tuple') and not (len(args) == 2 and isinstance(args[1], ast.Constant)):
                return ('T', tuple(self.ann(a) for a in args))
            if head == 'Optional' and len(args) == 1:
                t = self.ann(args[0])
                return ('C', t[1], True) if inst(t) else None
            if head in ('Iterator', 'Iterable', 'Generator') and args:
                return ('I', self.ann(args[0]))
        return None

    def functions(self):
        for m in self.models.values():
            for table in (m.methods, m.props, m.statics, m.classmethods, m.synth):
                yield from table.values()
        for f in self.funcs.values():
            yield f

    def infer(self):
        for _ in range(5):
            changed = False
            for fn in self.functions():
                owner, kind = self.owners[id(fn)]
                env = self.build_env(fn, owner, kind)
                self.envs[id(fn)] = env
                if id(fn) in self.fixed_ret:
                    continue
                values = [r.value for r in _walk_scope(fn) if isinstance(r, ast.Return)]
                ts = [self.typeof(v, env) if v is not None else 'none' for v in values]
                t = _unify(ts) if ts else 'none'
                key = (owner, self.method_name(fn)) if owner else fn.name
                table = self.mret if owner else self.fret
                if table.get(key) != t:
                    table[key] = t
                    changed = True
            for name, m in self.models.items():
                init = m.methods.get('__init__')
                if init is None or id(init) not in self.envs:
                    continue
                env = self.envs[id(init)]
                for each in _walk_scope(init):
                    if isinstance(each, (ast.Assign, ast.AnnAssign)):
                        targets = each.targets if isinstance(each, ast.Assign) else [each.target]
                        for t in targets:
                            if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                                    and t.value.id == 'self'):
                                ty = (self.ann(each.annotation) if isinstance(each, ast.AnnAssign) else None)
                                if ty is None or ty == ('L', None):
                                    vt = self.typeof(each.value, env) if each.value is not None else None
                                    ty = vt if ty is None or (isinstance(vt, tuple) and vt[0] == 'L') else ty
                                old = self.fields[name].get(t.attr)
                                if ty is not None and old != ty and (old is None or old == ('L', None)):
                                    self.fields[name][t.attr] = ty
                                    changed = True
                for attr, value in m.attrs.items():
                    ty = self.typeof(value, {})
                    if self.attr_types[name].get(attr) != ty:
                        self.attr_types[name][attr] = ty
                        changed = True
            if not changed:
                break

    def method_name(self, fn):
        owner = self.owners[id(fn)][0]
        m = self.models[owner]
        for table in (m.methods, m.props, m.statics, m.classmethods, m.synth):
            for k, v in table.items():
                if v is fn:
                    return k
        return fn.name

    def build_env(self, fn, owner, kind):
        fixed = {}
        for i, a in enumerate(fn.args.args):
            if i == 0 and owner is not None and kind == 'method':
                fixed[a.arg] = ('C', owner, False)
            elif i == 0 and owner is not None and kind == 'class':
                fixed[a.arg] = ('K', owner)
            else:
                t = self.ann(a.annotation)
                if t is not None:
                    fixed[a.arg] = t
        for each in _walk_scope(fn):
            if isinstance(each, ast.AnnAssign) and isinstance(each.target, ast.Name):
                t = self.ann(each.annotation)
                if t is not None and t != ('L', None):
                    fixed[each.target.id] = t
        env = dict(fixed)
        for _ in range(6):
            cands = {}

            def bind(target, t):
                if isinstance(target, ast.Name):
                    cands.setdefault(target.id, []).append(t)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    if isinstance(t, tuple) and t[0] == 'T' and len(t[1]) == len(target.elts):
                        for e, et in zip(target.elts, t[1]):
                            bind(e, et)
                    else:
                        el = self.elem(t)
                        for e in target.elts:
                            bind(e, el if not isinstance(e, ast.Starred) else None)
            for each in _walk_scope(fn):
                if isinstance(each, ast.Assign):
                    t = self.typeof(each.value, env)
                    for target in each.targets:
                        bind(target, t)
                elif isinstance(each, ast.AugAssign) and isinstance(each.target, ast.Name):
                    bind(each.target, self.typeof(ast.BinOp(left=each.target, op=each.op, right=each.value), env))
                elif isinstance(each, ast.AnnAssign) and isinstance(each.target, ast.Name) and each.value is not None:
                    bind(each.target, self.typeof(each.value, env))
                elif isinstance(each, (ast.For, ast.comprehension)):
                    bind(each.target, self.elem(self.typeof(each.iter, env)))
                elif isinstance(each, ast.With):
                    for item in each.items:
                        if item.optional_vars is not None:
                            bind(item.optional_vars, self.enter_type(self.typeof(item.context_expr, env)))
                elif (isinstance(each, ast.Call) and isinstance(each.func, ast.Attribute)
                      and each.func.attr == 'append' and isinstance(each.func.value, ast.Name) and len(each.args) == 1):
                    et = self.typeof(each.args[0], env)
                    cands.setdefault(each.func.value.id, []).append(('L', et) if et is not None else None)
            new = dict(fixed)
            for name, ts in cands.items():
                if name in fixed:
                    continue
                t = _unify(ts)
                if t is not None:
                    new[name] = t
            if new == env:
                break
            env = new
        return env

    def enter_type(self, t):
        if inst(t) and '__enter__' in self.models[t[1]].methods:
            return self.mret.get((t[1], '__enter__'))
        return None

    def iter_elem(self, cls):
        m = self.models[cls]
        fn = m.methods.get('__iter__')
        if fn is None:
            return None
        declared = self.ann(fn.returns)
        if isinstance(declared, tuple) and declared[0] == 'I' and declared[1] is not None:
            return declared[1]
        env = self.envs.get(id(fn), {'self': ('C', cls, False)})
        form = _iter_form(fn)
        if form[0] == 'iterable':
            return self.elem(self.typeof(form[1], env))
        if form[0] == 'generator':
            return _unify([self.typeof(y.value, env) for y in _walk_scope(fn) if isinstance(y, ast.Yield)
                           and y.value is not None])
        return None

    def elem(self, t):
        if not isinstance(t, tuple) and t != 'str':
            return None
        if t == 'str':
            return 'str'
        if t[0] in ('L', 'S', 'I'):
            return t[1]
        if t[0] == 'D':
            return t[1]
        if t[0] == 'T':
            return _unify(list(t[1]))
        if inst(t):
            return self.iter_elem(t[1])
        return None

    def method_ret(self, cls, method):
        return self.mret.get((cls, method))

    def typeof(self, e, env):
        try:
            return self._typeof(e, env)
        except RecursionError:
            return None

    def _typeof(self, e, env):
        T = lambda x: self.typeof(x, env)
        if isinstance(e, ast.Constant):
            v = e.value
            return ('bool' if isinstance(v, bool) else 'int' if isinstance(v, int) else 'float' if isinstance(v, float)
                    else 'str' if isinstance(v, str) else 'none' if v is None else None)
        if isinstance(e, ast.JoinedStr):
            return 'str'
        if isinstance(e, ast.Name):
            if e.id in env:
                return env[e.id]
            if e.id in self.models:
                return ('K', e.id)
            return None
        if isinstance(e, ast.Call):
            f = e.func
            if isinstance(f, ast.Name):
                n = f.id
                if n in env and isinstance(env[n], tuple) and env[n][0] == 'K':
                    return ('C', env[n][1], False)
                if n in self.models:
                    return ('C', n, False)
                if n in self.funcs:
                    return self.fret.get(n)
                if n in ('str', 'repr', 'input', 'chr', 'format', 'ascii'):
                    return 'str'
                if n in ('int', 'len', 'hash', 'ord'):
                    return 'int'
                if n == 'float':
                    return 'float'
                if n in ('bool', 'isinstance', 'any', 'all', 'callable'):
                    return 'bool'
                if n == 'abs' and e.args:
                    t = T(e.args[0])
                    if inst(t):
                        return self.method_ret(t[1], '__abs__')
                    return t if t in ('int', 'float') else None
                if n in ('sorted', 'list', 'reversed') and e.args:
                    return ('L', self.elem(T(e.args[0])))
                if n in ('max', 'min'):
                    if len(e.args) == 1:
                        return self.elem(T(e.args[0]))
                    return _unify([T(a) for a in e.args])
                if n == 'sum' and e.args:
                    el = self.elem(T(e.args[0]))
                    if len(e.args) == 2 and inst(T(e.args[1])):
                        return T(e.args[1])
                    return el if el in ('int', 'float') else None
                if n == 'enumerate' and e.args:
                    return ('L', ('T', ('int', self.elem(T(e.args[0])))))
                if n == 'zip':
                    return ('L', ('T', tuple(self.elem(T(a)) for a in e.args)))
                if n == 'range':
                    return ('L', 'int')
                if n == 'tuple' and e.args:
                    return ('L', self.elem(T(e.args[0])))
                if n == 'iter' and e.args:
                    return T(e.args[0])
                return None
            if isinstance(f, ast.Attribute):
                ot = T(f.value)
                if inst(ot):
                    m = self.models[ot[1]]
                    if f.attr in m.methods or f.attr in m.statics or f.attr in m.classmethods:
                        return self.method_ret(ot[1], f.attr)
                    if f.attr in m.synth:
                        return self.method_ret(ot[1], f.attr)
                    if f.attr in ('__str__', '__repr__'):
                        return 'str'
                    if f.attr in ('__eq__', '__ne__'):
                        return 'bool'
                    return None
                if isinstance(ot, tuple) and ot[0] == 'K':
                    m = self.models[ot[1]]
                    if f.attr in m.statics or f.attr in m.classmethods:
                        return self.method_ret(ot[1], f.attr)
                    return None
                if isinstance(ot, tuple) and ot[0] == 'L':
                    if f.attr == 'pop':
                        return ot[1]
                    if f.attr == 'copy':
                        return ot
                    if f.attr in ('index', 'count'):
                        return 'int'
                    return None
                if isinstance(ot, tuple) and ot[0] == 'D':
                    if f.attr in ('get', 'pop', 'setdefault'):
                        return ot[2]
                    if f.attr == 'values':
                        return ('L', ot[2])
                    if f.attr == 'keys':
                        return ('L', ot[1])
                    if f.attr == 'items':
                        return ('L', ('T', (ot[1], ot[2])))
                    if f.attr == 'copy':
                        return ot
                    return None
                if ot == 'str':
                    if f.attr in ('split', 'rsplit', 'splitlines'):
                        return ('L', 'str')
                    if f.attr in ('startswith', 'endswith') or f.attr.startswith('is'):
                        return 'bool'
                    if f.attr in ('find', 'rfind', 'index', 'rindex', 'count'):
                        return 'int'
                    return 'str'
            return None
        if isinstance(e, ast.Attribute):
            ot = T(e.value)
            if inst(ot):
                m = self.models[ot[1]]
                if e.attr in m.props:
                    return self.method_ret(ot[1], e.attr)
                if e.attr in self.fields[ot[1]]:
                    return self.fields[ot[1]][e.attr]
                if e.attr in m.attrs and e.attr not in m.instance_attrs:
                    return self.attr_types[ot[1]].get(e.attr)
                return None
            if isinstance(ot, tuple) and ot[0] == 'K':
                return self.attr_types[ot[1]].get(e.attr)
            return None
        if isinstance(e, ast.Subscript):
            vt = T(e.value)
            if isinstance(vt, tuple):
                if vt[0] == 'L':
                    return vt if isinstance(e.slice, ast.Slice) else vt[1]
                if vt[0] == 'D':
                    return vt[2]
                if vt[0] == 'T' and isinstance(e.slice, ast.Constant) and isinstance(e.slice.value, int):
                    try:
                        return vt[1][e.slice.value]
                    except IndexError:
                        return None
                if inst(vt) and '__getitem__' in self.models[vt[1]].methods:
                    return self.method_ret(vt[1], '__getitem__')
            if vt == 'str':
                return 'str'
            return None
        if isinstance(e, ast.BinOp):
            lt, rt = T(e.left), T(e.right)
            op = _BIN.get(type(e.op))
            if inst(lt) and self.models[lt[1]].has('__%s__' % op):
                return self.method_ret(lt[1], '__%s__' % op)
            if inst(rt) and not inst(lt) and self.models[rt[1]].has('__r%s__' % op):
                return self.method_ret(rt[1], '__r%s__' % op)
            if lt in ('int', 'float', 'bool') and rt in ('int', 'float', 'bool'):
                if isinstance(e.op, ast.Div):
                    return 'float'
                return 'float' if 'float' in (lt, rt) else 'int'
            if lt == 'str' and (rt == 'str' or isinstance(e.op, (ast.Mod, ast.Mult))):
                return 'str'
            if isinstance(lt, tuple) and lt[0] == 'L' and isinstance(e.op, (ast.Add, ast.Mult)):
                return lt
            return None
        if isinstance(e, ast.UnaryOp):
            if isinstance(e.op, ast.Not):
                return 'bool'
            t = T(e.operand)
            if inst(t):
                return self.method_ret(t[1], _UN[type(e.op)])
            return t if t in ('int', 'float') else 'int' if t == 'bool' else None
        if isinstance(e, ast.Compare):
            return 'bool'
        if isinstance(e, ast.BoolOp):
            return _unify([T(v) for v in e.values])
        if isinstance(e, ast.IfExp):
            return _unify([T(e.body), T(e.orelse)])
        if isinstance(e, ast.List):
            return ('L', _unify([T(x) for x in e.elts]) if e.elts else None)
        if isinstance(e, ast.Tuple):
            return ('T', tuple(T(x) for x in e.elts))
        if isinstance(e, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
            inner = dict(env)
            for g in e.generators:
                self._bind_comp(g.target, self.elem(self.typeof(g.iter, inner)), inner)
            t = self.typeof(e.elt, inner)
            return ('S', t) if isinstance(e, ast.SetComp) else ('L', t)
        if isinstance(e, ast.Dict):
            return ('D', _unify([T(k) for k in e.keys if k is not None]), _unify([T(v) for v in e.values]))
        if isinstance(e, ast.DictComp):
            inner = dict(env)
            for g in e.generators:
                self._bind_comp(g.target, self.elem(self.typeof(g.iter, inner)), inner)
            return ('D', self.typeof(e.key, inner), self.typeof(e.value, inner))
        if isinstance(e, ast.Set):
            return ('S', _unify([T(x) for x in e.elts]))
        return None

    def _bind_comp(self, target, t, env):
        if isinstance(target, ast.Name):
            if t is None:
                env.pop(target.id, None)
            else:
                env[target.id] = t
        elif isinstance(target, ast.Tuple):
            if isinstance(t, tuple) and t[0] == 'T' and len(t[1]) == len(target.elts):
                for e, et in zip(target.elts, t[1]):
                    self._bind_comp(e, et, env)
            else:
                for e in target.elts:
                    self._bind_comp(e, None, env)


def _iter_form(fn):
    """('iterable', E) when `__iter__` hands back an iterator over E (`return iter(E)`, `yield from E`,
    `for e in E: yield e`); ('generator', None) for any other generator body; ('other', None)."""
    body = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    if len(body) == 1:
        s = body[0]
        if (isinstance(s, ast.Return) and isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Name)
                and s.value.func.id == 'iter' and len(s.value.args) == 1 and not s.value.keywords):
            return ('iterable', s.value.args[0])
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.YieldFrom):
            return ('iterable', s.value.value)
        if (isinstance(s, ast.For) and isinstance(s.target, ast.Name) and not s.orelse and len(s.body) == 1
                and isinstance(s.body[0], ast.Expr) and isinstance(s.body[0].value, ast.Yield)
                and isinstance(s.body[0].value.value, ast.Name) and s.body[0].value.value.id == s.target.id):
            return ('iterable', s.iter)
    if any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in _walk_scope(fn)):
        return ('generator', None)
    return ('other', None)


def _nullable_classes(tree, models):
    out = set()
    for node in ast.walk(tree):
        ann = None
        if isinstance(node, ast.arg):
            ann = node.annotation
        elif isinstance(node, ast.AnnAssign):
            ann = node.annotation
        elif isinstance(node, (ast.FunctionDef,)):
            ann = node.returns
        ann = _ann_text(ann) if ann is not None else None
        if ann is None:
            continue
        for each in ast.walk(ann):
            if isinstance(each, ast.BinOp) and isinstance(each.op, ast.BitOr):
                for side in (each.left, each.right):
                    if isinstance(side, ast.Name) and side.id in models:
                        other = each.right if side is each.left else each.left
                        if isinstance(other, ast.Constant) and other.value is None or \
                                isinstance(other, ast.Name) and other.id == 'None':
                            out.add(side.id)
            if isinstance(each, ast.Subscript) and isinstance(each.value, ast.Name) and each.value.id == 'Optional':
                inner = _ann_text(each.slice)
                if isinstance(inner, ast.Name) and inner.id in models:
                    out.add(inner.id)
            if isinstance(each, ast.Constant) and isinstance(each.value, str) and each is not ann:
                sub = _ann_text(each)
                if sub is not None and sub is not each:
                    for s2 in ast.walk(sub):
                        if isinstance(s2, ast.Name) and s2.id in models and '| None' in each.value:
                            out.add(s2.id)
    return out


# -- the rewrite ---------------------------------------------------------------------------------------

class _Refuse(Exception):
    pass


class _Pass:
    def __init__(self, tree, models, unsupported):
        self.tree, self.models, self.Unsupported = tree, models, unsupported
        self.names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Name):
                self.names.add(n.id)
            elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                self.names.add(n.name)
            elif isinstance(n, ast.arg):
                self.names.add(n.arg)
        self.count = 0
        self.helpers = []            # new top-level defs: [(name, FunctionDef)]
        self.helper_names = {}       # key -> name
        self.after_class = {}        # class name -> statements placed after it
        self.static_names = {}       # (class, method) -> function name
        self.attr_names = {}         # (class, attr) -> module variable name
        self.changed = False
        self.used = {name: set() for name in models}    # lowered special methods actually reached

    def refuse(self, node, message):
        error = self.Unsupported(message)
        error.source_line = getattr(node, 'lineno', None)
        raise error

    def fresh(self, stem):
        while True:
            self.count += 1
            name = '_ail_du%d_%s' % (self.count, stem)
            if name not in self.names:
                self.names.add(name)
                return name

    def unique(self, name):
        while name in self.names:
            name += '_'
        self.names.add(name)
        return name

    # ---------------------------------------------------------------------------------------------
    def run(self):
        live = {n: m for n, m in self.models.items() if m.interesting()}
        bases = {b.id for m in self.models.values() for b in m.node.bases if isinstance(b, ast.Name)}
        for n in list(live):
            if n in bases:
                del live[n]
        if not live:
            return False
        self.live = live
        PURE_CALLS.clear()
        for name, m in self.models.items():
            init = m.methods.get('__init__')
            if init is not None and not any(isinstance(n, ast.Call) for n in ast.walk(init)):
                PURE_CALLS.add(name)
        for m in live.values():
            self.prepare_class(m)
        nullable = _nullable_classes(self.tree, self.models)
        self.nullable = nullable
        typer = _Typer(self.tree, {n: m for n, m in self.models.items()}, nullable)
        self.typer = typer
        typer.infer()
        # every function body, methods included (the class bodies were prepared above)
        for fn in list(typer.functions()):
            owner, kind = typer.owners[id(fn)]
            env = typer.envs.get(id(fn), {})
            _Rewriter(self, fn, env, owner).run()
        for m in live.values():
            for fn in m.classmethods.values():
                fn.args.args = fn.args.args[1:]     # cls: every use became the class itself
        while any(self.finish_class(m) for m in list(live.values())):
            pass
        for m in live.values():
            # every iteration was rewritten to what __iter__ iterates (a generator body is not a function here)
            if '__iter__' in m.methods:
                fn = m.methods.pop('__iter__')
                m.node.body = [s for s in m.node.body if s is not fn] or [_locate(ast.Pass(), m.node)]
        self.place()
        ast.fix_missing_locations(self.tree)
        for name, m in live.items():
            ACCEPTED[name] = (m.dunders() | set(m.synth)) & METHODS
            if m.has('__bool__') or m.has('__len__'):
                TRUTH.add(name)
        return True

    # -- classes ----------------------------------------------------------------------------------
    def prepare_class(self, m):
        c = m.node
        self.changed = True
        if m.total_ordering:
            self.total_ordering(m)
        for name, fn in list(m.methods.items()):
            if name in METHODS:
                self.prepare_dunder(m, name, fn)
        # class attributes -> module variables placed after the class
        placed = []
        for st in m.attr_nodes:
            if isinstance(st, ast.AnnAssign) and st.value is None:
                continue
            target = st.targets[0] if isinstance(st, ast.Assign) else st.target
            gname = self.unique('%s__%s' % (m.name, target.id))
            self.attr_names[(m.name, target.id)] = gname
        for st in m.attr_nodes:
            if isinstance(st, ast.AnnAssign) and st.value is None:
                continue
            target = st.targets[0] if isinstance(st, ast.Assign) else st.target
            value = _ClassScope(self, m).visit(copy.deepcopy(st.value))
            new = ast.Assign(targets=[ast.Name(id=self.attr_names[(m.name, target.id)], ctx=ast.Store())],
                             value=value)
            placed.append(_locate(new, st))
        self.after_class[m.name] = placed
        # static and class methods -> functions
        for table, kind in ((m.statics, 'static'), (m.classmethods, 'classmethod')):
            for name, fn in table.items():
                fname = self.unique('%s__%s__%s' % (m.name, kind, name))
                self.static_names[(m.name, name)] = fname
        for table, kind in ((m.statics, 'static'), (m.classmethods, 'classmethod')):
            for name, fn in table.items():
                fn.decorator_list = []
                if kind == 'classmethod':
                    if not fn.args.args:
                        self.refuse(fn, '@classmethod %s.%s takes no cls parameter' % (m.name, name))
                fn.name = self.static_names[(m.name, name)]
                self.helpers.append(fn)
        for name, fn in m.props.items():
            fn.decorator_list = []
        c.body = ([st for st in c.body if isinstance(st, ast.FunctionDef) and st.name in m.methods
                   or _binds_deferred(st, m)]
                  + [fn for fn in m.props.values()])
        if m.total_ordering:
            c.decorator_list = []
        if not c.body:
            c.body = [ast.Pass()]

    def total_ordering(self, m):
        """The orderings functools.total_ordering adds (CPython 3.12 functools: the root is the largest name
        among the defined ones, `__lt__` > `__le__` > `__gt__` > `__ge__`)."""
        roots = [op for op in ORDER if op in m.methods]
        if not roots:
            self.refuse(m.node, 'must define at least one ordering operation: < > <= >=')
        root = max(roots)
        conv = {
            '__lt__': [('__gt__', 'not r and self != other'), ('__le__', 'r or self == other'), ('__ge__', 'not r')],
            '__le__': [('__ge__', 'not r or self == other'), ('__lt__', 'r and self != other'), ('__gt__', 'not r')],
            '__gt__': [('__lt__', 'not r and self != other'), ('__ge__', 'r or self == other'), ('__le__', 'not r')],
            '__ge__': [('__le__', 'not r or self == other'), ('__gt__', 'r and self != other'), ('__lt__', 'not r')],
        }[root]
        base = m.methods[root]
        if not m.has('__eq__'):
            # object's own == and != are identity
            conv = [(op, body.replace('self != other', 'self is not other').replace('self == other', 'self is other'))
                    for op, body in conv]
        other = base.args.args[1].arg if len(base.args.args) > 1 else 'other'
        ann = base.args.args[1].annotation if len(base.args.args) > 1 else None
        for op, body in conv:
            if op in m.methods:
                continue
            text = 'def %s(self, %s):\n    r = self.%s(%s)\n    return %s\n' % (
                op, other, root, other, body.replace('other', other))
            fn = ast.parse(text).body[0]
            fn.args.args[1].annotation = copy.deepcopy(ann)
            fn.returns = ast.Name(id='bool', ctx=ast.Load())
            _locate(fn, base)
            m.methods[op] = fn
            m.node.body.append(fn)

    def prepare_dunder(self, m, name, fn):
        args = fn.args.args
        binary = (name in _SWAP or name in ('__contains__',)
                  or name[2:-2] in _BIN.values() or (name.startswith(('__r', '__i')) and name[3:-2] in _BIN.values()))
        if binary and len(args) == 2:
            a = args[1]
            ann = _ann_text(a.annotation) if a.annotation is not None else None
            loose = ann is None or (isinstance(ann, ast.Name) and ann.id in ('object', 'Any'))
            uses = any(isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == a.arg
                       for n in ast.walk(fn))
            guard = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'isinstance'
                        and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == a.arg
                        and isinstance(n.args[1], ast.Name) and n.args[1].id == m.name for n in ast.walk(fn))
            # `other` of a comparison, or one whose fields the body reads, is the class itself; a numeric
            # `other` (`self.x * k`) keeps what the body says
            if loose and (uses or guard or name in _SWAP):
                a.annotation = ast.Name(id=m.name, ctx=ast.Load())
        valued = any(isinstance(n, ast.Return) and n.value is not None for n in _walk_scope(fn))
        if fn.returns is None:
            if name in ('__str__', '__repr__'):
                fn.returns = ast.Name(id='__ail_checked_str__', ctx=ast.Load())
            elif name in ('__eq__', '__ne__', '__bool__', '__contains__') + ORDER and valued:
                fn.returns = ast.Name(id='bool', ctx=ast.Load())
            elif name in ('__len__', '__hash__'):
                fn.returns = ast.Name(id='__ail_checked_int__', ctx=ast.Load())
            elif not valued:
                fn.returns = ast.Name(id='__ail_checked_void__', ctx=ast.Load())
        if name == '__exit__':
            self.prepare_exit(m, fn)
        if name in ('__enter__',) and fn.returns is None and not valued:
            fn.returns = ast.Name(id='__ail_checked_void__', ctx=ast.Load())

    def prepare_exit(self, m, fn):
        """`__exit__(self, exc_type, exc, tb)` -> `__exit__(self, exc_type: int) -> bool`: the class arrives as
        the typed path's exception code (0: no exception), and every way out returns a bool."""
        args = fn.args.args
        if len(args) != 4:
            self.refuse(fn, '%s.__exit__ must take (self, exc_type, exc, tb)' % m.name)
        tname, vname, bname = args[1].arg, args[2].arg, args[3].arg
        fn.body = _ExitBody(self, tname, vname, bname).rewrite(fn.body)
        fn.args.args = [args[0], ast.arg(arg=tname, annotation=ast.Name(id='int', ctx=ast.Load()))]
        _locate(fn.args.args[1], fn)
        fn.returns = ast.Name(id='bool', ctx=ast.Load())
        if not fn.body or not isinstance(fn.body[-1], (ast.Return, ast.Raise)):
            fn.body.append(_locate(ast.Return(value=_const(False)), fn.body[-1] if fn.body else fn))
        m.exit_suppresses = any(isinstance(n, ast.Return) and not (isinstance(n.value, ast.Constant)
                                                                   and n.value.value in (False, None))
                                for n in _walk_scope(fn))

    def finish_class(self, m):
        """The dataclass methods some use asked for."""
        if m.dataclass is None:
            return False
        fields = list(m.fields)
        built = False
        for name in sorted(m.want):
            if name in m.methods:
                continue
            built = True
            if name == '__repr__':
                shown = [f for f in fields if f not in m.dataclass['hide']]
                parts = ', '.join('%s={self.%s!r}' % (f, f) for f in shown)
                text = 'def __repr__(self) -> __ail_checked_str__:\n    return f"%s(%s)"\n' % (m.name, parts.replace('"', '\\"'))
            elif name == '__eq__':
                cmp = [f for f in fields if f not in m.dataclass['nocmp']]
                body = ' and '.join('self.%s == other.%s' % (f, f) for f in cmp) or 'True'
                text = 'def __eq__(self, other: %s) -> bool:\n    return %s\n' % (m.name, body)
            else:
                continue
            fn = ast.parse(text).body[0]
            _locate(fn, m.node)
            m.methods[name] = fn
            m.synth[name] = fn
            m.node.body.append(fn)
            # the synthesized body itself may compare or show instances
            env = {'self': ('C', m.name, False), 'other': ('C', m.name, False)}
            self.typer.owners[id(fn)] = (m.name, 'method')
            _Rewriter(self, fn, env, m.name).run()
        return built

    def place(self):
        body = self.tree.body
        out = []
        for st in body:
            out.append(st)
            if isinstance(st, ast.ClassDef) and st.name in self.after_class:
                out.extend(self.after_class[st.name])
        defs = [i for i, st in enumerate(out) if isinstance(st, ast.FunctionDef)]
        helpers = [h for h in self.helpers]
        if helpers:
            at = defs[0] if defs else len(out)
            out[at:at] = helpers
        self.tree.body = out

    # -- helpers built on demand --------------------------------------------------------------------
    def helper(self, key, build):
        if key not in self.helper_names:
            name = self.unique(key)
            self.helper_names[key] = name
            fn = build(name)
            ast.fix_missing_locations(fn)
            self.helpers.append(fn)
        return self.helper_names[key]

    def len_check(self):
        def build(name):
            return ast.parse('def %s(n: int) -> __ail_checked_int__:\n'
                             '    if n < 0:\n'
                             '        raise ValueError("__len__() should return >= 0")\n'
                             '    return n\n' % name).body[0]
        return self.helper('_ail_du_len', build)


class _ClassScope(ast.NodeTransformer):
    """A class attribute's value may name an earlier attribute of the same class body."""

    def __init__(self, p, m):
        self.p, self.m = p, m

    def visit_Name(self, node):
        key = (self.m.name, node.id)
        if isinstance(node.ctx, ast.Load) and key in self.p.attr_names:
            return ast.copy_location(ast.Name(id=self.p.attr_names[key], ctx=ast.Load()), node)
        return node


class _ExitBody(ast.NodeTransformer):
    """`exc_type is None` -> `exc_type == 0`, `exc_type is ValueError` -> `exc_type == 1`,
    `issubclass(exc_type, ValueError)` -> one of its codes, `if exc_type:`; the exception value and the
    traceback may only be tested against None. A bare `return` / `return None` is `return False`."""

    def __init__(self, p, tname, vname, bname):
        self.p, self.t, self.v, self.b = p, tname, vname, bname

    def rewrite(self, body):
        return [self.visit(s) for s in body]

    def code_of(self, node):
        import pyfunc
        names = getattr(pyfunc, '_BUILTIN_EXC_NAMES', pyfunc.EXC_NAMES)   # EXC_NAMES is reset later in the compile
        if isinstance(node, ast.Name) and node.id in names and node.id != 'Exception':
            return names[node.id]
        return None

    def visit_Compare(self, node):
        if len(node.ops) == 1 and isinstance(node.left, ast.Name) and node.left.id in (self.t, self.v, self.b):
            op, right = node.ops[0], node.comparators[0]
            neg = isinstance(op, (ast.IsNot, ast.NotEq))
            if isinstance(op, (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)):
                if isinstance(right, ast.Constant) and right.value is None:
                    if node.left.id == self.b:
                        return ast.copy_location(_const(not neg), node)     # no traceback object here
                    test = ast.Compare(left=_name(self.t, synth=False), ops=[ast.NotEq() if neg else ast.Eq()],
                                       comparators=[_const(0)])
                    return ast.copy_location(test, node)
                code = self.code_of(right)
                if node.left.id == self.t and code is not None:
                    test = ast.Compare(left=_name(self.t, synth=False), ops=[ast.NotEq() if neg else ast.Eq()],
                                       comparators=[_const(code)])
                    return ast.copy_location(test, node)
        return self.generic_visit(node)

    def visit_Call(self, node):
        if (isinstance(node.func, ast.Name) and node.func.id == 'issubclass' and len(node.args) == 2
                and isinstance(node.args[0], ast.Name) and node.args[0].id == self.t):
            import pyfunc
            classes = node.args[1].elts if isinstance(node.args[1], ast.Tuple) else [node.args[1]]
            codes = []
            for k in classes:
                if isinstance(k, ast.Name) and k.id in ('Exception', 'BaseException'):
                    return ast.copy_location(ast.Compare(left=_name(self.t, synth=False), ops=[ast.NotEq()],
                                                         comparators=[_const(0)]), node)
                code = self.code_of(k)
                if code is None:
                    self.p.refuse(node, 'issubclass(%s, %s) in __exit__: not one of the built exception classes'
                                  % (self.t, ast.unparse(k)))
                codes.extend(pyfunc._handler_codes(code))
            test = ast.BoolOp(op=ast.Or(), values=[ast.Compare(left=_name(self.t, synth=False), ops=[ast.Eq()],
                                                               comparators=[_const(c)]) for c in codes])
            return ast.copy_location(test if len(codes) > 1 else test.values[0], node)
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in (self.v, self.b) and isinstance(node.ctx, ast.Load):
            self.p.refuse(node, '__exit__ uses %r other than in `is None` / `is not None`; the exception '
                          'value and its traceback are not values here' % node.id)
        if node.id == self.t and isinstance(node.ctx, ast.Load):
            node._exit_type = True
        return node

    def visit_If(self, node):
        node = self.generic_visit(node)
        if isinstance(node.test, ast.Name) and node.test.id == self.t:
            node.test = ast.copy_location(ast.Compare(left=_name(self.t, synth=False), ops=[ast.NotEq()],
                                                      comparators=[_const(0)]), node.test)
        return node

    def visit_Return(self, node):
        if node.value is None or (isinstance(node.value, ast.Constant) and node.value.value is None):
            return ast.copy_location(ast.Return(value=_const(False)), node)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        return node


# -- the per-function rewrite -----------------------------------------------------------------------------

class _Rewriter(ast.NodeTransformer):
    def __init__(self, p, fn, env, owner):
        self.p, self.fn, self.env, self.owner = p, fn, env, owner
        self.typer = p.typer
        self.models = p.models
        self.globals_needed = set()
        self.folded = False

    # helpers
    def T(self, node):
        return self.typer.typeof(node, self.env)

    def model(self, t):
        if inst(t) and t[1] in self.p.live:
            return self.p.live[t[1]]
        return None

    def kmodel(self, t):
        if isinstance(t, tuple) and t[0] == 'K' and t[1] in self.p.live:
            return self.p.live[t[1]]
        return None

    def has(self, t, method):
        m = self.model(t)
        if m is None:
            return False
        if method in ('__eq__', '__repr__') and m.dataclass is not None and method not in m.methods:
            if method == '__eq__' and m.dataclass['noeq'] or method == '__repr__' and m.dataclass['norepr']:
                return False
            m.want.add(method)
            return True
        return method in m.methods

    def nullable(self, t):
        return inst(t) and (t[2] or t[1] in self.p.nullable)

    def refuse(self, node, message):
        self.p.refuse(node, message)

    def run(self):
        fn = self.fn
        fn.body = self.block(fn.body)
        if self.globals_needed:
            have = {n for g in fn.body if isinstance(g, ast.Global) for n in g.names}
            need = sorted(self.globals_needed - have)
            if need:
                fn.body.insert(0, _locate(ast.Global(names=need), fn.body[0] if fn.body else fn))
        if self.folded:
            fn.body = _fold_block(fn.body) or [_locate(ast.Pass(), fn)]

    # -- statements ---------------------------------------------------------------------------------
    def block(self, stmts):
        out = []
        for st in stmts:
            new = self.stmt(st)
            if isinstance(new, list):
                out.extend(new)
            elif new is not None:
                out.append(new)
        return out

    def stmt(self, st):
        if isinstance(st, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            return st
        if isinstance(st, ast.If):
            st.test = self.truth(st.test)
            st.body = self.block(st.body)
            st.orelse = self.block(st.orelse)
            return st
        if isinstance(st, ast.While):
            st.test = self.truth(st.test)
            st.body = self.block(st.body)
            st.orelse = self.block(st.orelse)
            return st
        if isinstance(st, ast.Assert):
            st.test = self.truth(st.test)
            if st.msg is not None:
                st.msg = self.visit(st.msg)
            return st
        if isinstance(st, ast.For):
            return self.for_stmt(st)
        if isinstance(st, ast.With):
            return self.with_stmt(st)
        if isinstance(st, ast.Try):
            st.body = self.block(st.body)
            for h in st.handlers:
                h.body = self.block(h.body)
            st.orelse = self.block(st.orelse)
            st.finalbody = self.block(st.finalbody)
            return st
        if isinstance(st, ast.Assign):
            return self.assign(st)
        if isinstance(st, ast.AugAssign):
            return self.aug_assign(st)
        if isinstance(st, ast.AnnAssign):
            if st.value is not None:
                st.value = self.visit(st.value)
            st.target = self.target(st.target)
            return st
        if isinstance(st, ast.Delete):
            st.targets = [self.target(t) for t in st.targets]
            return st
        if isinstance(st, ast.Expr) and self.print_needs_order(st.value):
            # print() evaluates every argument before it calls any __str__: bind them in order first
            call = st.value
            pre, args = [], []
            for a in call.args:
                if isinstance(a, ast.Constant):
                    args.append(a)
                    continue
                tmp = self.p.fresh('arg')
                self.env[tmp] = self.T(a)
                pre.append(_locate(ast.Assign(targets=[_name(tmp, True)], value=a), st))
                args.append(_locate(_name(tmp), a))
            for k in call.keywords:
                if not isinstance(k.value, ast.Constant):
                    tmp = self.p.fresh('kw')
                    self.env[tmp] = self.T(k.value)
                    pre.append(_locate(ast.Assign(targets=[_name(tmp, True)], value=k.value), st))
                    k.value = _locate(_name(tmp), k.value)
            call.args = args
            return self.block(pre) + [self.visit(st)]
        return self.visit(st)

    def print_needs_order(self, call):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'print'):
            return False
        if any(isinstance(a, ast.Starred) for a in call.args):
            return False
        shown = [i for i, a in enumerate(call.args)
                 if self.model(self.T(a)) is not None or self.list_of_shown(self.T(a))]
        if not shown:
            return False
        later = call.args[shown[0] + 1:] + [k.value for k in call.keywords]
        return not all(_calls_only_pure(x) for x in later)

    def target(self, t):
        """An assignment target: `C.attr` / `self.attr` naming a class attribute becomes its module variable."""
        if isinstance(t, ast.Attribute):
            gname = self.class_attr(t)
            if gname is not None:
                self.globals_needed.add(gname)
                self.p.changed = True
                return ast.copy_location(ast.Name(id=gname, ctx=t.ctx), t)
            t.value = self.visit(t.value)
            return t
        if isinstance(t, ast.Subscript):
            self.check_keys(t)
            t.value = self.visit(t.value)
            t.slice = self.visit(t.slice)
            return t
        if isinstance(t, (ast.Tuple, ast.List)):
            t.elts = [self.target(e) for e in t.elts]
            return t
        if isinstance(t, ast.Starred):
            t.value = self.target(t.value)
            return t
        return t

    def class_attr(self, node):
        """The module variable an Attribute names when it is a class attribute (read through the class, cls,
        or an instance that has no instance attribute of that name), else None."""
        if not isinstance(node, ast.Attribute):
            return None
        vt = self.T(node.value)
        km = self.kmodel(vt)
        if km is not None and (km.name, node.attr) in self.p.attr_names:
            return self.p.attr_names[(km.name, node.attr)]
        m = self.model(vt)
        if (m is not None and (m.name, node.attr) in self.p.attr_names and node.attr not in m.instance_attrs
                and isinstance(node.ctx, ast.Load)):
            if not _pure(node.value):
                self.refuse(node, 'a class attribute read through %s; read it as %s.%s'
                            % (ast.unparse(node.value), m.name, node.attr))
            return self.p.attr_names[(m.name, node.attr)]
        return None

    def assign(self, st):
        if len(st.targets) == 1 and isinstance(st.targets[0], ast.Subscript):
            t = st.targets[0]
            vt = self.T(t.value)
            if self.has(vt, '__setitem__'):
                if isinstance(t.slice, ast.Slice):
                    self.refuse(t, 'a slice assigned into a %s (__setitem__ with a slice object)' % vt[1])
                self.p.used[vt[1]].add('__setitem__')
                receiver, key, value = self.visit(t.value), self.visit(t.slice), self.visit(st.value)
                pre = []
                if not (_pure(st.value) or (_pure(t.value) and _pure(t.slice))):
                    tmp = self.p.fresh('v')
                    pre.append(_locate(ast.Assign(targets=[_name(tmp, True)], value=value), st))
                    value = _name(tmp)
                call = ast.Expr(value=_mcall(receiver, '__setitem__', [key, value]))
                return pre + [_locate(call, st)]
        if len(st.targets) == 1 and isinstance(st.targets[0], (ast.Tuple, ast.List)):
            # `a, b = x` unpacks through __iter__
            new = self.iter_arg(st.value, self.T(st.value))
            if new is not None:
                st.value = new
                st.targets = [self.target(st.targets[0])]
                return st
        st.value = self.visit(st.value)
        st.targets = [self.target(t) for t in st.targets]
        return st

    def aug_assign(self, st):
        op = _BIN[type(st.op)]
        t = st.target
        if isinstance(t, ast.Attribute):
            km = self.kmodel(self.T(t.value))
            if km is not None and (km.name, t.attr) in self.p.attr_names:
                # C.attr op= v rebinds the class attribute (self.attr op= v would make an instance one)
                gname = self.p.attr_names[(km.name, t.attr)]
                self.globals_needed.add(gname)
                self.p.changed = True
                new = ast.AugAssign(target=ast.Name(id=gname, ctx=ast.Store()), op=st.op, value=self.visit(st.value))
                return _locate(new, st)
        tt = self.T(t)
        vt = self.T(st.value)
        m = self.model(tt)
        method = None
        if m is not None:
            if self.has(tt, '__i%s__' % op):
                method = '__i%s__' % op
            elif self.has(tt, '__%s__' % op):
                method = '__%s__' % op
        if method is None and isinstance(t, ast.Subscript):
            ct = self.T(t.value)
            if self.has(ct, '__getitem__') and self.has(ct, '__setitem__'):
                if not (_pure(t.value) and _pure(t.slice)):
                    self.refuse(st, 'an augmented assignment into %s[...] with a computed receiver or key'
                                % ct[1])
                self.p.used[ct[1]].update(('__getitem__', '__setitem__'))
                read = ast.Subscript(value=copy.deepcopy(t.value), slice=copy.deepcopy(t.slice), ctx=ast.Load())
                value = self.visit(_locate(ast.BinOp(left=read, op=st.op, right=st.value), st))
                call = ast.Expr(value=_mcall(self.visit(t.value), '__setitem__', [self.visit(t.slice), value]))
                return _locate(call, st)
        if method is None and inst(vt) and not inst(tt) and tt is not None and self.has(vt, '__r%s__' % op):
            method = 'r'
        if method is None:
            st.value = self.visit(st.value)
            st.target = self.target(st.target)
            return st
        # x op= y  ->  x = x.__iop__(y)  (or __op__, or y.__rop__(x))
        if isinstance(t, ast.Name):
            read = _name(t.id, synth=False)
        elif isinstance(t, (ast.Attribute, ast.Subscript)) and _pure(t):
            read = copy.deepcopy(t)
            read.ctx = ast.Load()
        else:
            self.refuse(st, 'an augmented assignment to %s, whose target is computed' % ast.unparse(t))
        self.p.changed = True
        if method == 'r':
            self.p.used[vt[1]].add('__r%s__' % op)
            value = _mcall(self.visit(st.value), '__r%s__' % op, [self.visit(read)])
        else:
            self.p.used[tt[1]].add(method)
            value = _mcall(self.visit(read), method, [self.visit(st.value)])
        new = ast.Assign(targets=[self.target(copy.deepcopy(t))], value=value)
        return _locate(new, st)

    # -- for loops over __iter__ ------------------------------------------------------------------
    def for_stmt(self, st):
        it = self.T(st.iter)
        m = self.model(it)
        if m is not None and '__iter__' in m.methods:
            fn = m.methods['__iter__']
            form = _iter_form(fn)
            self.p.used[m.name].add('__iter__')
            if form[0] == 'iterable':
                st.iter = self.substitute(form[1], st.iter, st)
                st.iter = self.visit(st.iter)
                st.target = self.target(st.target)
                st.body = self.block(st.body)
                st.orelse = self.block(st.orelse)
                return st
            if form[0] == 'generator':
                return self.inline_generator(st, m, fn)
            self.refuse(st, 'iterating a %s: its __iter__ is not `return iter(...)` or a generator '
                        '(an iterator class with __next__ is not built)' % m.name)
        st.iter = self.visit(st.iter)
        st.target = self.target(st.target)
        st.body = self.block(st.body)
        st.orelse = self.block(st.orelse)
        return st

    def substitute(self, expr, receiver, where):
        """`expr` (an `__iter__` result written over `self`) with `self` replaced by `receiver`."""
        expr = copy.deepcopy(expr)
        uses = [n for n in ast.walk(expr) if isinstance(n, ast.Name) and n.id == 'self']
        if len(uses) > 1 and not _pure(receiver):
            self.refuse(where, 'iterating a computed receiver whose __iter__ reads self twice; bind it to a name')
        others = {n.id for n in ast.walk(expr) if isinstance(n, ast.Name) and n.id != 'self'}
        if others - set(self.p.typer.funcs) - set(self.models) - {'iter', 'sorted', 'list', 'reversed', 'range', 'len'}:
            self.refuse(where, '__iter__ reads names other than self')

        class Sub(ast.NodeTransformer):
            def visit_Name(s, node):
                if node.id == 'self':
                    return copy.deepcopy(receiver)
                return node
        out = Sub().visit(expr)
        return _locate(out, where)

    def generator_body(self, fn, where):
        """The generator body of `fn`, checked for the shapes inlining keeps exact."""
        body = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
        for n in _walk_scope(ast.Module(body=body, type_ignores=[])):
            if isinstance(n, ast.Return):
                self.refuse(where, 'a return inside the generator __iter__ of %s' % self.owner_name(fn))
            if isinstance(n, (ast.Try, ast.With)):
                self.refuse(where, 'a try or with inside the generator __iter__ of %s' % self.owner_name(fn))
            if isinstance(n, ast.YieldFrom):
                self.refuse(where, 'yield from inside a longer generator __iter__')
        for n in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(n, (ast.Lambda, ast.FunctionDef, ast.Global, ast.Nonlocal)):
                self.refuse(where, 'a nested function, lambda or global inside the generator __iter__')
        for n in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(n, ast.Yield):
                if n.value is None:
                    self.refuse(where, 'a bare yield in __iter__')
        # every yield must be a statement of its own
        stmt_yields = {id(s.value) for s in ast.walk(ast.Module(body=body, type_ignores=[]))
                       if isinstance(s, ast.Expr) and isinstance(s.value, ast.Yield)}
        for n in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(n, ast.Yield) and id(n) not in stmt_yields:
                self.refuse(where, 'a yield used as a value in __iter__')
        return body

    def owner_name(self, fn):
        return self.typer.owners.get(id(fn), ('?',))[0]

    def renamed_generator(self, m, fn, receiver, where):
        """The generator body with its locals renamed fresh and `self` bound to `receiver` first."""
        body = copy.deepcopy(self.generator_body(fn, where))
        local = set()
        for n in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                local.add(n.id)
        mapping = {name: self.p.fresh('g_' + name) for name in sorted(local)}
        selfname = self.p.fresh('self')
        mapping['self'] = selfname

        class Ren(ast.NodeTransformer):
            def visit_Name(s, node):
                if node.id in mapping:
                    new = _name(mapping[node.id], isinstance(node.ctx, ast.Store))
                    new.ctx = node.ctx
                    return ast.copy_location(new, node)
                return node
        body = [Ren().visit(s) for s in body]
        head = _locate(ast.Assign(targets=[_name(selfname, True)], value=receiver), where)
        return head, body

    def inline_generator(self, st, m, fn):
        receiver = self.visit(st.iter)
        head, gbody = self.renamed_generator(m, fn, receiver, st)
        target = st.target
        body = self.block(st.body)
        orelse = self.block(st.orelse)
        loops = (ast.For, ast.While)

        def own_jumps(stmts):
            found = []

            def scan(nodes):
                for n in nodes:
                    if isinstance(n, (ast.Break, ast.Continue)):
                        found.append(n)
                    elif isinstance(n, loops):
                        continue
                    elif isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                        continue
                    else:
                        for field in ('body', 'orelse', 'finalbody', 'handlers'):
                            sub = getattr(n, field, None)
                            if isinstance(sub, list):
                                scan(sub)
            scan(stmts)
            return found
        jumps = own_jumps(body)
        flag = None
        if jumps or orelse:
            flag = self.p.fresh('brk')

        def body_at_yield(value_node, origin):
            assign = _locate(ast.Assign(targets=[copy.deepcopy(target)], value=value_node), origin)
            inner = copy.deepcopy(body)
            if flag is None:
                return [assign] + inner
            # break -> set the flag and leave the one-pass loop; continue -> leave it (back to the generator)

            class Jumps(ast.NodeTransformer):
                def visit_Break(s, node):
                    return [_locate(ast.Assign(targets=[_name(flag, True)], value=_const(True)), node),
                            _locate(ast.Break(), node)]

                def visit_For(s, node):
                    return node

                def visit_While(s, node):
                    return node

                def visit_FunctionDef(s, node):
                    return node
            inner = [Jumps().visit(s) for s in inner]
            flat = []
            for s in inner:
                flat.extend(s if isinstance(s, list) else [s])
            once = ast.For(target=_name(self.p.fresh('once'), True), iter=_call(_name('range', synth=False), [_const(1)]),
                           body=flat or [ast.Pass()], orelse=[])
            exit_ = ast.If(test=_name(flag), body=[ast.Break()], orelse=[])
            return [assign, _locate(once, origin), _locate(exit_, origin)]

        def expand(stmts):
            out = []
            for s in stmts:
                if isinstance(s, ast.Expr) and isinstance(s.value, ast.Yield):
                    out.extend(body_at_yield(s.value.value, s))
                    continue
                if isinstance(s, (ast.If,)):
                    s.body = expand(s.body)
                    s.orelse = expand(s.orelse)
                elif isinstance(s, loops):
                    has_yield = any(isinstance(n, ast.Yield) for n in ast.walk(s))
                    s.body = expand(s.body)
                    s.orelse = expand(s.orelse)
                    out.append(s)
                    if has_yield and flag is not None:
                        out.append(_locate(ast.If(test=_name(flag), body=[ast.Break()], orelse=[]), s))
                    continue
                out.append(s)
            return out
        gbody = expand(gbody)
        self.p.changed = True
        if flag is None:
            return [head] + _locate(gbody, st)
        init = _locate(ast.Assign(targets=[_name(flag, True)], value=_const(False)), st)
        top = ast.For(target=_name(self.p.fresh('top'), True), iter=_call(_name('range', synth=False), [_const(1)]),
                      body=gbody or [ast.Pass()], orelse=[])
        out = [init, head, _locate(top, st)]
        if orelse:
            out.append(_locate(ast.If(test=_not(_name(flag)), body=orelse, orelse=[]), st))
        return out

    def materialize(self, node, t):
        """An eager consumer's argument `node` (an instance of a class with an `__iter__`) as a list: an
        `iterable` __iter__ gives its iterable, a generator runs into a list in a helper function."""
        m = self.model(t)
        fn = m.methods['__iter__']
        form = _iter_form(fn)
        self.p.used[m.name].add('__iter__')
        if form[0] == 'iterable':
            return self.visit(self.substitute(form[1], node, node))
        if form[0] != 'generator':
            self.refuse(node, 'iterating a %s: its __iter__ is not `return iter(...)` or a generator' % m.name)
        typer = self.typer
        elem = typer.iter_elem(m.name)

        def build(name):
            body = copy.deepcopy(self.generator_body(fn, node))
            out = '_ail_out'

            class Y(ast.NodeTransformer):
                def visit_Expr(s, e):
                    if isinstance(e.value, ast.Yield):
                        return ast.copy_location(ast.Expr(value=_mcall(_name(out), 'append', [e.value.value])), e)
                    return e
            body = [Y().visit(s) for s in body]
            fn2 = ast.FunctionDef(name=name, args=ast.arguments(posonlyargs=[], args=[
                ast.arg(arg='self', annotation=ast.Name(id=m.name, ctx=ast.Load()))], vararg=None,
                kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
                body=[], decorator_list=[], returns=None)
            ann = _type_ann(elem)
            init = (ast.AnnAssign(target=_name(out, True), annotation=ast.Subscript(
                        value=ast.Name(id='list', ctx=ast.Load()), slice=ann, ctx=ast.Load()),
                        value=ast.List(elts=[], ctx=ast.Load()), simple=1) if ann is not None
                    else ast.Assign(targets=[_name(out, True)], value=ast.List(elts=[], ctx=ast.Load())))
            fn2.body = [init] + body + [ast.Return(value=_name(out))]
            if ann is not None:
                fn2.returns = (ast.Name(id='__ail_checked_flist__', ctx=ast.Load()) if elem == 'float' else
                               ast.Subscript(value=ast.Name(id='__ail_checked_list', ctx=ast.Load()),
                                             slice=copy.deepcopy(ann), ctx=ast.Load()))
            _locate(fn2, fn)
            # the body itself may use special methods
            env = typer.build_env(fn2, None, 'function')
            env['self'] = ('C', m.name, False)
            typer.owners[id(fn2)] = (None, 'function')
            _Rewriter(self.p, fn2, env, None).run()
            return fn2
        name = self.p.helper('_ail_du_iter_%s' % m.name, build)
        self.p.changed = True
        return _locate(_call(_name(name, synth=False), [self.visit(node)]), node)

    # -- with ---------------------------------------------------------------------------------------
    def with_stmt(self, st):
        if len(st.items) > 1:
            inner = ast.With(items=st.items[1:], body=st.body, type_comment=None)
            _locate(inner, st)
            st.items = st.items[:1]
            st.body = [inner]
        item = st.items[0]
        t = self.T(item.context_expr)
        m = self.model(t)
        if m is None or '__enter__' not in m.methods or '__exit__' not in m.methods:
            item.context_expr = self.visit(item.context_expr)
            if item.optional_vars is not None:
                item.optional_vars = self.target(item.optional_vars)
            st.body = self.block(st.body)
            return st
        self.p.used[m.name].update(('__enter__', '__exit__'))
        self.p.changed = True
        mgr = self.p.fresh('mgr')
        out = [_locate(ast.Assign(targets=[_name(mgr, True)], value=self.visit(item.context_expr)), st)]
        enter = _mcall(_name(mgr), '__enter__')
        enter_void = isinstance(m.methods['__enter__'].returns, ast.Name) and \
            m.methods['__enter__'].returns.id in ('__ail_checked_void__', 'None')
        if item.optional_vars is not None:
            if enter_void:
                self.refuse(st, '%s.__enter__ returns nothing; `with ... as` would bind None' % m.name)
            out.append(_locate(ast.Assign(targets=[self.target(item.optional_vars)], value=enter), st))
        else:
            out.append(_locate(ast.Expr(value=enter), st))
        body = self.block(st.body)
        if not getattr(m, 'exit_suppresses', True) and not self.exit_reads_type(m):
            # __exit__ never suppresses and never looks at the exception: a finally is exact
            fin = ast.Expr(value=_mcall(_name(mgr), '__exit__', [_const(0)]))
            out.append(_locate(ast.Try(body=body or [ast.Pass()], handlers=[], orelse=[], finalbody=[fin]), st))
            return out
        flag = self.p.fresh('exc')
        code = self.p.fresh('code')
        handler_body = [
            ast.Assign(targets=[_name(code, True)], value=_call(_name('__ail_exc_code__', synth=False))),
            ast.Assign(targets=[_name(flag, True)], value=_const(True)),
            ast.If(test=_not(_mcall(_name(mgr), '__exit__', [_name(code)])), body=[ast.Raise(exc=None, cause=None)],
                   orelse=[]),
        ]
        handler = ast.ExceptHandler(type=ast.Name(id=ANY_EXCEPTION, ctx=ast.Load()), name=None,
                                    body=handler_body)
        inner = ast.Try(body=body or [ast.Pass()], handlers=[handler], orelse=[], finalbody=[])
        fin = ast.If(test=_not(_name(flag)), body=[ast.Expr(value=_mcall(_name(mgr), '__exit__', [_const(0)]))],
                     orelse=[])
        outer = ast.Try(body=[inner], handlers=[], orelse=[], finalbody=[fin])
        out.insert(0, _locate(ast.Assign(targets=[_name(flag, True)], value=_const(False)), st))
        out.append(_locate(outer, st))
        return out

    def exit_reads_type(self, m):
        fn = m.methods['__exit__']
        tname = fn.args.args[1].arg
        return any(isinstance(n, ast.Name) and n.id == tname for s in fn.body for n in ast.walk(s))

    # -- truth -------------------------------------------------------------------------------------
    def truth(self, node):
        if isinstance(node, ast.BoolOp):
            node.values = [self.truth(v) for v in node.values]
            return node
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            node.operand = self.truth(node.operand)
            return node
        t = self.T(node)
        m = self.model(t)
        if m is not None and (m.has('__bool__') or m.has('__len__')):
            value = self.visit(node)
            if self.nullable(t):
                if not _pure(node):
                    self.refuse(node, 'the truth value of a %s that may be None, computed in place; bind it to '
                                'a name first' % m.name)
                test = self.truth_call(m, copy.deepcopy(value))
                return _locate(ast.BoolOp(op=ast.And(), values=[
                    ast.Compare(left=value, ops=[ast.IsNot()], comparators=[_const(None)]), test]), node)
            return _locate(self.truth_call(m, value), node)
        return self.visit(node)

    def truth_call(self, m, value):
        self.p.changed = True
        if m.has('__bool__'):
            self.p.used[m.name].add('__bool__')
            return _mcall(value, '__bool__')
        self.p.used[m.name].add('__len__')
        return ast.Compare(left=_call(_name(self.p.len_check(), synth=False), [_mcall(value, '__len__')]),
                           ops=[ast.NotEq()], comparators=[_const(0)])

    # -- expressions -------------------------------------------------------------------------------
    def visit_IfExp(self, node):
        node.test = self.truth(node.test)
        node.body = self.visit(node.body)
        node.orelse = self.visit(node.orelse)
        return node

    def visit_comprehension(self, node, eager=False):
        """One `for ... in ... if ...` of a comprehension: the iterable in the scope so far, then the
        target is bound (in `self.env`) for the conditions."""
        it = self.T(node.iter)
        m = self.model(it)
        if eager and m is not None and '__iter__' in m.methods:
            # a generator may run ahead of the comprehension only when neither has a side effect to interleave
            eager = all(_calls_only_pure(s, yields=True) for s in m.methods['__iter__'].body)
        node.iter = self.iter_arg(node.iter, it, eager=eager) or self.visit(node.iter)
        self.typer._bind_comp(node.target, self.typer.elem(it), self.env)
        node.ifs = [self.truth(c) for c in node.ifs]
        return node

    def comp(self, node):
        """Comprehension expressions see their own loop variables."""
        saved = self.env
        inner = dict(self.env)
        for g in node.generators:
            self.typer._bind_comp(g.target, self.typer.elem(self.typer.typeof(g.iter, inner)), inner)
        # the iterables are typed in the enclosing scope (first) / growing scope (rest)
        new_gens = []
        scope = dict(saved)
        parts = ([node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]) + \
            [c for g in node.generators for c in g.ifs] + [g.iter for g in node.generators[1:]]
        eager = all(_calls_only_pure(x) for x in parts)
        self.env = scope
        for g in node.generators:
            new_gens.append(self.visit_comprehension(g, eager))     # binds g.target in scope
        node.generators = new_gens
        self.env = inner
        try:
            if isinstance(node, ast.DictComp):
                node.key = self.visit(node.key)
                node.value = self.visit(node.value)
            else:
                node.elt = self.visit(node.elt)
        finally:
            self.env = saved
        return node

    visit_ListComp = visit_SetComp = visit_GeneratorExp = visit_DictComp = comp

    def visit_Lambda(self, node):
        saved = self.env
        self.env = {k: v for k, v in self.env.items() if k not in {a.arg for a in node.args.args}}
        try:
            node.body = self.visit(node.body)
        finally:
            self.env = saved
        return node

    def visit_BinOp(self, node):
        lt, rt = self.T(node.left), self.T(node.right)
        if isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            return self.percent(node)
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        op = _BIN[type(node.op)]
        if self.has(lt, '__%s__' % op):
            self.p.used[lt[1]].add('__%s__' % op)
            self.p.changed = True
            return _locate(_mcall(node.left, '__%s__' % op, [node.right]), node)
        if (inst(rt) and not inst(lt) and lt is not None and self.has(rt, '__r%s__' % op)):
            if not (_pure(node.left) or _pure(node.right)):
                self.refuse(node, 'a reflected %s (%s.__r%s__) between two computed operands; bind one to a name'
                            % (type(node.op).__name__, rt[1], op))
            self.p.used[rt[1]].add('__r%s__' % op)
            self.p.changed = True
            return _locate(_mcall(node.right, '__r%s__' % op, [node.left]), node)
        return node

    def visit_UnaryOp(self, node):
        if isinstance(node.op, ast.Not):
            node.operand = self.truth(node.operand)
            return node
        t = self.T(node.operand)
        node.operand = self.visit(node.operand)
        method = _UN[type(node.op)]
        if self.has(t, method):
            self.p.used[t[1]].add(method)
            self.p.changed = True
            return _locate(_mcall(node.operand, method), node)
        return node

    def tuple_compare(self, node):
        """`(a0, a1) < (b0, b1)` of two equal-length tuple displays of plain numbers or str (the usual ordering
        key of a __lt__): the first unequal pair decides, as tuple comparison does."""
        l, r, op = node.left, node.comparators[0], node.ops[0]
        if not (isinstance(l, ast.Tuple) and isinstance(r, ast.Tuple) and len(l.elts) == len(r.elts) >= 1
                and isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq))):
            return None
        pairs = list(zip(l.elts, r.elts))
        num = ('int', 'float', 'bool')
        for a, b in pairs:
            ta, tb = self.T(a), self.T(b)
            if not (_pure(a) and _pure(b) and (ta in num and tb in num or ta == tb == 'str')):
                return None
        pairs = [(self.visit(a), self.visit(b)) for a, b in pairs]
        if not all(_pure(a) and _pure(b) for a, b in pairs):
            self.refuse(node, 'a tuple comparison whose elements read a property; bind them to names first')
        cmp = lambda a, o, b: ast.Compare(left=copy.deepcopy(a), ops=[o], comparators=[copy.deepcopy(b)])
        if isinstance(op, (ast.Eq, ast.NotEq)):
            parts = [cmp(a, type(op)(), b) for a, b in pairs]
            out = parts[0] if len(parts) == 1 else ast.BoolOp(op=ast.And() if isinstance(op, ast.Eq) else ast.Or(),
                                                             values=parts)
            return _locate(out, node)
        out = cmp(pairs[-1][0], type(op)(), pairs[-1][1])
        for a, b in reversed(pairs[:-1]):
            out = ast.IfExp(test=cmp(a, ast.NotEq(), b), body=cmp(a, type(op)(), b), orelse=out)
        self.p.changed = True
        return _locate(out, node)

    def visit_Compare(self, node):
        if len(node.ops) == 1 and isinstance(node.left, ast.Tuple):
            lowered = self.tuple_compare(node)
            if lowered is not None:
                return lowered
        types = [self.T(x) for x in [node.left] + node.comparators]
        if not any(self.model(t) is not None for t in types):
            return self.generic_visit(node)
        operands = [node.left] + node.comparators
        if len(node.ops) > 1:
            if not all(_pure(x) for x in operands[1:-1]):
                self.refuse(node, 'a chained comparison of class instances with a computed middle operand')
            parts = []
            for i, op in enumerate(node.ops):
                pair = ast.Compare(left=copy.deepcopy(operands[i]), ops=[op], comparators=[copy.deepcopy(operands[i + 1])])
                parts.append(self.visit_Compare(_locate(pair, node)))
            return _locate(ast.BoolOp(op=ast.And(), values=parts), node)
        op = node.ops[0]
        l, r = node.left, node.comparators[0]
        lt, rt = types
        if isinstance(op, (ast.Is, ast.IsNot)):
            return self.generic_visit(node)
        if isinstance(op, (ast.In, ast.NotIn)):
            m = self.model(rt)
            if isinstance(rt, tuple) and rt[0] == 'L' and self.has(rt[1], '__eq__'):
                # `x in xs` over instances: each element `e is x or e == x`, in order (list.__contains__)
                name = self.list_helper('in', self.model(rt[1]))
                self.p.changed = True
                call = _call(_name(name, synth=False), [self.visit(l), self.visit(r)])
                return _locate(_not(call) if isinstance(op, ast.NotIn) else call, node)
            if m is not None:
                if self.has(rt, '__contains__'):
                    if not (_pure(l) or _pure(r)):
                        self.refuse(node, '`in` a %s with two computed operands; bind one to a name' % m.name)
                    self.p.used[m.name].add('__contains__')
                    self.p.changed = True
                    fn = m.methods['__contains__']
                    call = _mcall(self.visit(r), '__contains__', [self.visit(l)])
                    if not (isinstance(fn.returns, ast.Name) and fn.returns.id in ('bool', '__ail_checked_bool__')):
                        call = _call(_name('bool', synth=False), [call])
                    return _locate(_not(call) if isinstance(op, ast.NotIn) else call, node)
                if '__iter__' in m.methods and _iter_form(m.methods['__iter__'])[0] == 'iterable':
                    node.left = self.visit(l)
                    node.comparators = [self.materialize(r, rt)]
                    return node
            return self.generic_visit(node)
        name = _CMP[type(op)]
        if isinstance(op, (ast.Eq, ast.NotEq)):
            if self.has(lt, '__eq__') or self.has(lt, '__ne__'):
                if isinstance(r, ast.Constant) and r.value is None:
                    self.refuse(node, 'comparing a %s, which defines __eq__, with None; write `is None`' % lt[1])
                if lt[2]:
                    self.refuse(node, '`==` on a %s that may be None (None == x does not call __eq__); test '
                                '`is None` first' % lt[1])
                left, right = self.visit(l), self.visit(r)
                self.p.changed = True
                if isinstance(op, ast.NotEq) and self.has(lt, '__ne__') and '__ne__' in self.model(lt).methods:
                    self.p.used[lt[1]].add('__ne__')
                    return _locate(_mcall(left, '__ne__', [right]), node)
                if not self.has(lt, '__eq__'):
                    return self.generic_visit(node)
                self.p.used[lt[1]].add('__eq__')
                call = _mcall(left, '__eq__', [right])
                return _locate(_not(call) if isinstance(op, ast.NotEq) else call, node)
            if (self.model(rt) is not None and self.has(rt, '__eq__') and isinstance(l, ast.Constant)
                    and l.value is None):
                self.refuse(node, 'comparing None with a %s, which defines __eq__; write `is None`' % rt[1])
            return self.generic_visit(node)
        if self.has(lt, name):
            self.p.used[lt[1]].add(name)
            self.p.changed = True
            return _locate(_mcall(self.visit(l), name, [self.visit(r)]), node)
        if self.has(rt, _SWAP[name]) and not self.has(lt, name):
            if not (_pure(l) or _pure(r)):
                self.refuse(node, 'a reflected comparison (%s.%s) between two computed operands' % (rt[1], _SWAP[name]))
            self.p.used[rt[1]].add(_SWAP[name])
            self.p.changed = True
            return _locate(_mcall(self.visit(r), _SWAP[name], [self.visit(l)]), node)
        return self.generic_visit(node)

    # -- instances that compare by value cannot be keys of the typed path's tables -------------------------
    def hashed(self, t):
        """An instance whose class compares by value (__eq__, a dataclass's __eq__, or __hash__): the typed
        path's sets and dicts would key it by identity."""
        m = self.model(t)
        return m is not None and (m.has('__eq__') or '__hash__' in m.methods)

    def refuse_key(self, node, t, where):
        self.refuse(node, '%s instance as %s: a set element or dict key that compares with __eq__ / __hash__ '
                    'is not built on the typed path (its tables key an instance by identity)' % (t[1], where))

    def check_keys(self, node):
        """Refuse a set or dict use keyed by such an instance, before any rewrite of the node."""
        if isinstance(node, (ast.Set, ast.SetComp)):
            elts = node.elts if isinstance(node, ast.Set) else [node.elt]
            env = self.env
            if isinstance(node, ast.SetComp):
                env = dict(self.env)
                for g in node.generators:
                    self.typer._bind_comp(g.target, self.typer.elem(self.typer.typeof(g.iter, env)), env)
            for e in elts:
                t = self.typer.typeof(e, env)
                if self.hashed(t):
                    self.refuse_key(node, t, 'a set element')
        elif isinstance(node, (ast.Dict, ast.DictComp)):
            keys = node.keys if isinstance(node, ast.Dict) else [node.key]
            env = self.env
            if isinstance(node, ast.DictComp):
                env = dict(self.env)
                for g in node.generators:
                    self.typer._bind_comp(g.target, self.typer.elem(self.typer.typeof(g.iter, env)), env)
            for k in keys:
                if k is not None and self.hashed(self.typer.typeof(k, env)):
                    self.refuse_key(node, self.typer.typeof(k, env), 'a dict key')
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in ('set', 'frozenset', 'dict', 'Counter') and node.args:
                et = self.typer.elem(self.T(node.args[0]))
                if self.hashed(et):
                    self.refuse_key(node, et, 'a set element' if f.id != 'dict' else 'a dict key')
            if isinstance(f, ast.Attribute) and node.args and f.attr in (
                    'add', 'discard', 'remove', 'get', 'setdefault', 'pop', 'count', 'index', 'fromkeys'):
                at = self.T(node.args[0])
                rt = self.T(f.value)
                if self.hashed(at) and not (isinstance(rt, tuple) and rt[0] == 'L') and self.model(rt) is None:
                    self.refuse_key(node, at, 'the argument of .%s()' % f.attr)
        elif isinstance(node, ast.Compare):
            operands = [node.left] + node.comparators
            for op, l, r in zip(node.ops, operands, operands[1:]):
                if isinstance(op, (ast.In, ast.NotIn)):
                    lt, rt = self.T(l), self.T(r)
                    if self.hashed(lt) and not (isinstance(rt, tuple) and rt[0] == 'L') and self.model(rt) is None:
                        self.refuse_key(node, lt, 'the left operand of `in`')
        elif isinstance(node, ast.Subscript):
            st, vt = self.T(node.slice), self.T(node.value)
            if self.hashed(st) and self.model(vt) is None:
                self.refuse_key(node, st, 'a subscript')

    def visit(self, node):
        if isinstance(node, (ast.Set, ast.SetComp, ast.Dict, ast.DictComp, ast.Call, ast.Compare, ast.Subscript)):
            self.check_keys(node)
        return super().visit(node)

    def visit_Subscript(self, node):
        if isinstance(node.ctx, ast.Load):
            vt = self.T(node.value)
            if self.has(vt, '__getitem__'):
                if isinstance(node.slice, ast.Slice):
                    self.refuse(node, 'slicing a %s (__getitem__ with a slice object)' % vt[1])
                self.p.used[vt[1]].add('__getitem__')
                self.p.changed = True
                return _locate(_mcall(self.visit(node.value), '__getitem__', [self.visit(node.slice)]), node)
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Load):
            gname = self.class_attr(node)
            if gname is not None:
                self.p.changed = True
                return ast.copy_location(ast.Name(id=gname, ctx=ast.Load()), node)
            vt = self.T(node.value)
            m = self.model(vt)
            if m is not None and node.attr in m.props:
                self.p.changed = True
                return _locate(_mcall(self.visit(node.value), node.attr), node)
            km = self.kmodel(vt)
            if km is not None and node.attr not in km.statics and node.attr not in km.classmethods \
                    and node.attr not in km.methods and node.attr not in km.deferred:
                self.refuse(node, '%s.%s is not a class attribute of %s' % (km.name, node.attr, km.name))
        return self.generic_visit(node)

    def visit_FormattedValue(self, node):
        t = self.T(node.value)
        conv = node.conversion
        if self.model(t) is not None or self.list_of_shown(t):
            if node.format_spec is not None:
                self.refuse(node, 'a format spec on a %s in an f-string (__format__ is not built)' % self.tname(t))
            if conv == 97:
                self.refuse(node, 'ascii() of a %s' % self.tname(t))
            value = self.show(node.value, t, repr_=conv == 114)
            if value is not None:
                node.value = value
                node.conversion = -1
                return node
        node.value = self.visit(node.value)
        if node.format_spec is not None:
            node.format_spec = self.visit(node.format_spec)
        return node

    def tname(self, t):
        return t[1] if inst(t) else 'list'

    def list_of_shown(self, t):
        if isinstance(t, tuple) and t[0] == 'L' and self.model(t[1]) is not None:
            return True
        if isinstance(t, tuple) and t[0] == 'T' and any(self.model(x) is not None for x in t[1]):
            return True
        return False

    def show(self, node, t, repr_=False):
        """`str(node)` (or `repr(node)`) as a call of the instance's own method; None when not built."""
        m = self.model(t)
        if m is not None:
            if not repr_ and self.has(t, '__str__'):
                method = '__str__'
            elif self.has(t, '__repr__'):
                method = '__repr__'
            else:
                return None
            self.p.used[m.name].add(method)
            self.p.changed = True
            if self.nullable(t) and (_pure(node) or t[2]):
                # a value that may be None shows as "None"
                if not _pure(node):
                    self.refuse(node, 'showing a computed %s that may be None; bind it to a name first' % m.name)
                value = self.visit(node)
                return _locate(ast.IfExp(test=ast.Compare(left=copy.deepcopy(value), ops=[ast.Is()],
                                                          comparators=[_const(None)]),
                                         body=_const('None'), orelse=_mcall(value, method)), node)
            return _locate(_mcall(self.visit(node), method), node)
        if isinstance(t, tuple) and t[0] == 'L' and self.model(t[1]) is not None:
            em = self.model(t[1])
            if not self.has(t[1], '__repr__'):
                return None
            self.p.used[em.name].add('__repr__')
            name = self.p.helper('_ail_du_list_repr_%s' % em.name, lambda name: ast.parse(
                'def %s(xs: list[%s]) -> __ail_checked_str__:\n'
                '    out: list[str] = []\n'
                '    for x in xs:\n'
                '        out.append(x.__repr__())\n'
                '    return "[" + ", ".join(out) + "]"\n' % (name, em.name)).body[0])
            self.p.changed = True
            return _locate(_call(_name(name, synth=False), [self.visit(node)]), node)
        if isinstance(t, tuple) and t[0] == 'T' and isinstance(node, ast.Tuple):
            parts = []
            for e, et in zip(node.elts, t[1]):
                s = self.show(e, et, repr_=True) if (self.model(et) is not None or self.list_of_shown(et)) else None
                if s is None:
                    if et in ('int', 'float', 'bool') or et == 'str':
                        s = ast.JoinedStr(values=[ast.FormattedValue(value=self.visit(e), conversion=114,
                                                                     format_spec=None)])
                    else:
                        return None
                parts.append(s)
            if not parts:
                return None
            text = [_const('(')]
            for i, s in enumerate(parts):
                if i:
                    text.append(_const(', '))
                text.append(s)
            text.append(_const(',)' if len(parts) == 1 else ')'))
            out = text[0]
            for s in text[1:]:
                out = ast.BinOp(left=out, op=ast.Add(), right=s)
            return _locate(out, node)
        return None

    def percent(self, node):
        fmt = node.left.value
        args = node.right.elts if isinstance(node.right, ast.Tuple) else [node.right]
        types = [self.T(a) for a in args]
        if not any(self.model(t) is not None or self.list_of_shown(t) for t in types):
            return self.generic_visit(node)
        if '%(' in fmt:
            self.refuse(node, 'a %%(name) format with a class instance')
        first = min(i for i, t in enumerate(types) if self.model(t) is not None or self.list_of_shown(t))
        if not all(_calls_only_pure(a) for a in args[first + 1:]):
            # CPython builds the whole tuple before it calls __str__; here the call takes the instance's place
            self.refuse(node, 'a %-format whose arguments after a class instance call functions; bind them to '
                        'names first')
        directive = re.compile(r'%([#0\- +]*)(\*|\d+)?(?:\.(\*|\d+))?([hlL]?)([diouxXeEfFgGcrsa%])')
        pieces, new_args, i, last = [], [], 0, 0
        for mt in directive.finditer(fmt):
            pieces.append(fmt[last:mt.start()])
            last = mt.end()
            if mt.group(5) == '%':
                pieces.append(mt.group(0))
                continue
            if mt.group(2) == '*' or mt.group(3) == '*':
                self.refuse(node, 'a * width in a %-format with a class instance')
            if i >= len(args):
                return self.generic_visit(node)
            a, t = args[i], types[i]
            i += 1
            if (self.model(t) is not None or self.list_of_shown(t)) and mt.group(5) in 'rs':
                shown = self.show(a, t, repr_=mt.group(5) == 'r')
                if shown is None:
                    return self.generic_visit(node)
                new_args.append(shown)
                pieces.append(mt.group(0)[:-1] + 's')
            else:
                new_args.append(self.visit(a))
                pieces.append(mt.group(0))
        pieces.append(fmt[last:])
        if i != len(args):
            return self.generic_visit(node)
        node.left = ast.copy_location(_const(''.join(pieces)), node.left)
        if isinstance(node.right, ast.Tuple):
            node.right.elts = new_args
        else:
            node.right = new_args[0]
        return node

    def str_format(self, node):
        fmt = node.func.value.value
        types = [self.T(a) for a in node.args]
        if not any(self.model(t) is not None or self.list_of_shown(t) for t in types):
            return None
        if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
            self.refuse(node, 'str.format with keywords or *args and a class instance')
        try:
            fields = list(string.Formatter().parse(fmt))
        except ValueError:
            return None
        # CPython evaluates every argument, then formats the fields in order (calling __str__ there). With
        # arguments that run no code, one argument per field, in field order, is the same program.
        if not all(_calls_only_pure(a) for a in node.args):
            self.refuse(node, 'str.format with a class instance and arguments that call functions; bind the '
                        'arguments to names first')
        auto, out, slots = 0, [], []
        for literal, field, spec, conv in fields:
            out.append(literal.replace('{', '{{').replace('}', '}}'))
            if field is None:
                continue
            if field == '':
                index = auto
                auto += 1
            elif field.isdigit():
                index = int(field)
            else:
                self.refuse(node, 'a named or attribute field in str.format with a class instance')
            if index >= len(node.args) or '{' in (spec or ''):
                return None
            t = types[index]
            if self.model(t) is not None or self.list_of_shown(t):
                if spec:
                    self.refuse(node, 'a format spec on a %s in str.format (__format__ is not built)' % self.tname(t))
                if conv == 'a':
                    self.refuse(node, 'ascii() of a %s' % self.tname(t))
                shown = self.show(copy.deepcopy(node.args[index]), t, repr_=conv == 'r')
                if shown is None:
                    return None
                out.append('{%d}' % len(slots))
                slots.append(shown)
            else:
                out.append('{%d%s%s}' % (len(slots), ('!' + conv) if conv else '', (':' + spec) if spec else ''))
                slots.append(self.visit(copy.deepcopy(node.args[index])))
        node.func.value = ast.copy_location(_const(''.join(out)), node.func.value)
        node.args = [_locate(s, node) for s in slots]
        return node

    def key_function(self, kw, elem_t):
        """`key=abs` / `key=len` / `key=str` / `key=repr` over instances -> a lambda calling the method; a key
        lambda's parameter is an element."""
        m = self.model(elem_t)
        if m is None:
            return
        if isinstance(kw.value, ast.Lambda) and len(kw.value.args.args) == 1:
            saved = self.env
            self.env = dict(self.env)
            self.env[kw.value.args.args[0].arg] = elem_t
            try:
                kw.value.body = self.visit(kw.value.body)
            finally:
                self.env = saved
            kw._ail_du_done = True
            return
        if not (isinstance(kw.value, ast.Name) and kw.value.id in ('abs', 'len', 'str', 'repr')):
            return
        var = self.p.fresh('k')
        body = _call(_name(kw.value.id, synth=False), [_name(var)])
        lam = ast.Lambda(args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=var, annotation=None)], vararg=None,
                                            kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]), body=body)
        saved = self.env
        self.env = dict(self.env)
        self.env[var] = elem_t
        try:
            lam.body = self.visit(lam.body)
        finally:
            self.env = saved
        kw.value = _locate(lam, kw.value)
        kw._ail_du_done = True
        self.p.changed = True

    def finish_call(self, node, first_iter=False, lazy_iter=False):
        """Visit a call's parts once, leaving the keywords a key function already rewrote; an iterated argument
        that is an instance with __iter__ becomes what it iterates (`lazy_iter`: only an `iterable` one)."""
        node.func = self.visit(node.func)
        args = []
        for i, a in enumerate(node.args):
            new = None
            if (first_iter and i == 0) or lazy_iter:
                new = self.iter_arg(a, self.T(a), eager=not lazy_iter)
            if new is None:
                new = self.visit(a)
            args.extend(new if isinstance(new, list) else [new])
        node.args = args
        node.keywords = [k if getattr(k, '_ail_du_done', False) else self.visit(k) for k in node.keywords]
        return node

    def iter_arg(self, node, t, eager=True):
        """An argument iterated by its consumer: an instance with __iter__ becomes what it iterates."""
        m = self.model(t)
        if m is None or '__iter__' not in m.methods:
            return None
        form = _iter_form(m.methods['__iter__'])
        if form[0] == 'generator' and not eager:
            return None
        return self.materialize(node, t)

    def visit_Starred(self, node):
        """`*x` in a call or a display; a generator __iter__ that is only `yield e` statements over a plain
        receiver spreads into those expressions (each evaluated where the unpacking evaluates it)."""
        t = self.T(node.value)
        m = self.model(t)
        if m is not None and '__iter__' in m.methods and _pure(node.value):
            fn = m.methods['__iter__']
            body = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
            if body and all(isinstance(s, ast.Expr) and isinstance(s.value, ast.Yield) and s.value.value is not None
                            and _calls_only_pure(s.value.value) for s in body):
                self.p.used[m.name].add('__iter__')
                self.p.changed = True
                return [self.visit(self.substitute(s.value.value, node.value, node)) for s in body]
        new = self.iter_arg(node.value, t)
        node.value = new if new is not None else self.visit(node.value)
        return node

    def visit_Call(self, node):
        f = node.func
        if isinstance(f, ast.Name):
            n = f.id
            args = node.args
            if n == 'isinstance' and len(args) == 2:
                t = self.T(args[0])
                classes = args[1].elts if isinstance(args[1], ast.Tuple) else [args[1]]
                if inst(t) and all(isinstance(k, ast.Name) for k in classes):
                    names = {k.id for k in classes}
                    if t[1] in self.models and (names <= set(self.models) or t[1] in names):
                        self.folded = True
                        self.p.changed = True
                        if t[1] in names:
                            if self.nullable(t):
                                if not _pure(args[0]):
                                    self.refuse(node, 'isinstance() of a computed value that may be None')
                                return _locate(ast.Compare(left=self.visit(args[0]), ops=[ast.IsNot()],
                                                           comparators=[_const(None)]), node)
                            return _locate(_const(True), node)
                        if _pure(args[0]):
                            return _locate(_const(False), node)
            if len(args) == 1 and not node.keywords:
                t = self.T(args[0])
                m = self.model(t)
                if n == 'len' and m is not None and self.has(t, '__len__'):
                    self.p.used[m.name].add('__len__')
                    self.p.changed = True
                    return _locate(_call(_name(self.p.len_check(), synth=False),
                                         [_mcall(self.visit(args[0]), '__len__')]), node)
                if n in ('str', 'repr') and (m is not None or self.list_of_shown(t)):
                    shown = self.show(args[0], t, repr_=n == 'repr')
                    if shown is not None:
                        return shown
                if n == 'bool' and m is not None and (m.has('__bool__') or m.has('__len__')):
                    return _locate(self.truth(args[0]), node)
                if n == 'abs' and m is not None and self.has(t, '__abs__'):
                    self.p.used[m.name].add('__abs__')
                    self.p.changed = True
                    return _locate(_mcall(self.visit(args[0]), '__abs__'), node)
                if n == 'hash' and m is not None:
                    self.refuse(node, 'hash() of a %s instance: instances as set elements or dict keys '
                                '(__hash__) are not built on the typed path' % m.name)
                if n in ('list', 'tuple', 'sum', 'set', 'frozenset') and m is not None:
                    new = self.iter_arg(args[0], t)
                    if new is not None:
                        node.args = [new]
                        node.func = self.visit(node.func)
                        return node
                if n in ('iter', 'next') and m is not None:
                    self.refuse(node, '%s() of a %s instance (the iterator protocol is not built)' % (n, m.name))
            if n == 'sum' and len(args) == 2 and not node.keywords:
                st = self.T(args[1])
                sm = self.model(st)
                if sm is not None and self.has(st, '__add__') and self.typer.method_ret(sm.name, '__add__') in (
                        ('C', sm.name, False),):
                    src = self.T(args[0])
                    if self.typer.elem(src) is not None:
                        # sum(xs, start): start + x for each x, left to right
                        self.p.used[sm.name].add('__add__')
                        name = self.p.helper('_ail_du_sum_%s' % sm.name, lambda name: ast.parse(
                            'def %s(xs: list[%s], start: %s) -> __ail_checked_%s__:\n'
                            '    acc = start\n'
                            '    for x in xs:\n'
                            '        acc = acc.__add__(x)\n'
                            '    return acc\n' % (name, sm.name, sm.name, sm.name)).body[0])
                        first = self.iter_arg(args[0], src)
                        self.p.changed = True
                        return _locate(_call(_name(name, synth=False),
                                             [first if first is not None else self.visit(args[0]),
                                              self.visit(args[1])]), node)
            if n == 'print':
                new_args = []
                for a in node.args:
                    if isinstance(a, ast.Starred):
                        new = self.visit_Starred(a)
                        new_args.extend(new if isinstance(new, list) else [new])
                        continue
                    t = self.T(a)
                    if self.model(t) is not None or self.list_of_shown(t):
                        shown = self.show(a, t)
                        new_args.append(shown if shown is not None else self.visit(a))
                    else:
                        new_args.append(self.visit(a))
                node.args = new_args
                node.keywords = [self.visit(k) for k in node.keywords]
                return node
            if n in ('sorted', 'min', 'max') and node.args:
                elem = self.typer.elem(self.T(node.args[0])) if len(node.args) == 1 else None
                for kw in node.keywords:
                    if kw.arg == 'key':
                        self.key_function(kw, elem)
                if self.model(elem) is not None and not any(kw.arg == 'key' for kw in node.keywords):
                    return self.ordered(node, n, elem)
                if n in ('min', 'max') and len(node.args) > 1 and any(self.model(self.T(a)) for a in node.args) \
                        and not node.keywords:
                    return self.minmax_args(node, n)
                return self.finish_call(node, first_iter=len(node.args) == 1)
            if n in ('enumerate', 'zip', 'any', 'all') and node.args:
                return self.finish_call(node, lazy_iter=True)
        if isinstance(f, ast.Attribute):
            if isinstance(f.value, ast.Constant) and isinstance(f.value.value, str) and f.attr == 'format':
                new = self.str_format(node)
                if new is not None:
                    return new
            vt = self.T(f.value)
            km, m = self.kmodel(vt), self.model(vt)
            owner = km or m
            if owner is not None and f.attr in self.p.static_names and False:
                pass
            if owner is not None and (owner.name, f.attr) in self.p.static_names and (
                    f.attr in owner.statics or f.attr in owner.classmethods):
                if m is not None and not _pure(f.value):
                    self.refuse(node, 'a static or class method called through a computed instance; call it '
                                'as %s.%s(...)' % (owner.name, f.attr))
                self.p.changed = True
                fname = self.p.static_names[(owner.name, f.attr)]
                return _locate(ast.Call(func=_name(fname, synth=False), args=[self.visit(a) for a in node.args],
                                        keywords=[self.visit(k) for k in node.keywords]), node)
            if km is not None and f.attr in km.methods and node.args:
                # C.method(obj, ...) -> obj.method(...)
                self.p.changed = True
                return _locate(_mcall(self.visit(node.args[0]), f.attr, [self.visit(a) for a in node.args[1:]]), node)
            if m is not None and f.attr == 'sort' and not node.args:
                pass
            lt = vt
            if isinstance(lt, tuple) and lt[0] == 'L' and self.model(lt[1]) is not None and f.attr == 'sort':
                for kw in node.keywords:
                    if kw.arg == 'key':
                        self.key_function(kw, lt[1])
                if not any(kw.arg == 'key' for kw in node.keywords):
                    return self.sort_in_place(node, lt[1])
                return self.finish_call(node)
            if isinstance(lt, tuple) and lt[0] == 'L' and self.model(lt[1]) is not None and \
                    f.attr in ('index', 'count', 'remove') and self.has(lt[1], '__eq__'):
                if len(node.args) != 1 or node.keywords:
                    self.refuse(node, 'list.%s() over %s instances with a start or stop' % (f.attr, lt[1][1]))
                name = self.list_helper(f.attr, self.model(lt[1]))
                self.p.changed = True
                return _locate(_call(_name(name, synth=False), [self.visit(f.value), self.visit(node.args[0])]), node)
        if isinstance(f, ast.Name) and f.id in self.env and self.kmodel(self.env[f.id]) is not None:
            # cls(...) in a class method
            km = self.kmodel(self.env[f.id])
            self.p.changed = True
            return _locate(ast.Call(func=ast.Name(id=km.name, ctx=ast.Load()), args=[self.visit(a) for a in node.args],
                                    keywords=[self.visit(k) for k in node.keywords]), node)
        return self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.env and self.kmodel(self.env[node.id]) is not None:
            self.refuse(node, '%r (the class itself) used as a value; only cls(...), cls.attribute and '
                        'cls.method(...) are built' % node.id)
        return node

    def list_helper(self, what, m):
        """`x in xs`, `xs.index(x)`, `xs.count(x)`, `xs.remove(x)` over a list of instances of `m`, which
        compares with __eq__: each element `e is x or e.__eq__(x)`, as list's own methods do."""
        self.p.used[m.name].add('__eq__')
        c = m.name
        text = {
            'in': ('def %%s(x: %s, xs: list[%s]) -> bool:\n'
                   '    for e in xs:\n'
                   '        if e is x or e.__eq__(x):\n'
                   '            return True\n'
                   '    return False\n' % (c, c)),
            'index': ('def %%s(xs: list[%s], x: %s) -> __ail_checked_int__:\n'
                      '    i = 0\n'
                      '    while i < len(xs):\n'
                      '        e = xs[i]\n'
                      '        if e is x or e.__eq__(x):\n'
                      '            return i\n'
                      '        i += 1\n'
                      '    raise ValueError("list.index(x): x not in list")\n' % (c, c)),
            'count': ('def %%s(xs: list[%s], x: %s) -> __ail_checked_int__:\n'
                      '    n = 0\n'
                      '    for e in xs:\n'
                      '        if e is x or e.__eq__(x):\n'
                      '            n += 1\n'
                      '    return n\n' % (c, c)),
            'remove': ('def %%s(xs: list[%s], x: %s) -> __ail_checked_void__:\n'
                       '    i = 0\n'
                       '    while i < len(xs):\n'
                       '        e = xs[i]\n'
                       '        if e is x or e.__eq__(x):\n'
                       '            xs.pop(i)\n'
                       '            return\n'
                       '        i += 1\n'
                       '    raise ValueError("list.remove(x): x not in list")\n' % (c, c)),
        }[what]
        return self.p.helper('_ail_du_%s_%s' % (what, c), lambda name: ast.parse(text % name).body[0])

    # -- ordering of lists of instances ----------------------------------------------------------------
    def less(self, m, a, b):
        """The source of `a < b` for two instances of `m`, as CPython chooses: __lt__, or the reflected __gt__."""
        if m.has('__lt__'):
            self.p.used[m.name].add('__lt__')
            return '%s.__lt__(%s)' % (a, b)
        if m.has('__gt__'):
            self.p.used[m.name].add('__gt__')
            return '%s.__gt__(%s)' % (b, a)
        return None

    def greater(self, m, a, b):
        if m.has('__gt__'):
            self.p.used[m.name].add('__gt__')
            return '%s.__gt__(%s)' % (a, b)
        if m.has('__lt__'):
            self.p.used[m.name].add('__lt__')
            return '%s.__lt__(%s)' % (b, a)
        return None

    def sort_helper(self, m, node):
        less = self.less(m, 'b', 'a')
        if less is None:
            self.refuse(node, 'sorting %s instances, which define no __lt__ (or __gt__)' % m.name)

        def build(name):
            # a stable merge sort comparing with `<` only, as list.sort does (the result is the same for any
            # consistent ordering; the number and order of the comparisons differ from timsort)
            return ast.parse(
                'def %s(xs: list[%s]) -> __ail_checked_void__:\n'
                '    n = len(xs)\n'
                '    if n < 2:\n'
                '        return\n'
                '    buf: list[%s] = xs.copy()\n'
                '    width = 1\n'
                '    while width < n:\n'
                '        lo = 0\n'
                '        while lo < n:\n'
                '            mid = min(lo + width, n)\n'
                '            hi = min(lo + 2 * width, n)\n'
                '            i = lo\n'
                '            j = mid\n'
                '            k = lo\n'
                '            while i < mid and j < hi:\n'
                '                a = xs[i]\n'
                '                b = xs[j]\n'
                '                if %s:\n'
                '                    buf[k] = b\n'
                '                    j += 1\n'
                '                else:\n'
                '                    buf[k] = a\n'
                '                    i += 1\n'
                '                k += 1\n'
                '            while i < mid:\n'
                '                buf[k] = xs[i]\n'
                '                i += 1\n'
                '                k += 1\n'
                '            while j < hi:\n'
                '                buf[k] = xs[j]\n'
                '                j += 1\n'
                '                k += 1\n'
                '            lo += 2 * width\n'
                '        for t in range(n):\n'
                '            xs[t] = buf[t]\n'
                '        width *= 2\n' % (name, m.name, m.name, less)).body[0]
        return self.p.helper('_ail_du_sort_%s' % m.name, build)

    def sort_in_place(self, node, elem):
        m = self.model(elem)
        reverse = None
        for kw in node.keywords:
            if kw.arg == 'reverse':
                reverse = kw.value
            elif kw.arg != 'key':
                return self.generic_visit(node)
        helper = self.sort_helper(m, node)
        target = self.visit(node.func.value)
        self.p.changed = True
        if reverse is None or (isinstance(reverse, ast.Constant) and not reverse.value):
            return _locate(_call(_name(helper, synth=False), [target]), node)
        if not (isinstance(reverse, ast.Constant) and reverse.value is True):
            self.refuse(node, 'sort(reverse=<computed>) of %s instances' % m.name)
        # reverse=True keeps equal elements in their original order: reverse, sort, reverse
        rev = self.p.helper('_ail_du_rsort_%s' % m.name, lambda name: ast.parse(
            'def %s(xs: list[%s]) -> __ail_checked_void__:\n    xs.reverse()\n    %s(xs)\n    xs.reverse()\n'
            % (name, m.name, helper)).body[0])
        if not _pure(node.func.value):
            self.refuse(node, 'sort(reverse=True) of a computed list of %s instances' % m.name)
        return _locate(_call(_name(rev, synth=False), [target]), node)

    def ordered(self, node, n, elem):
        m = self.model(elem)
        if n == 'sorted':
            reverse = False
            for kw in node.keywords:
                if kw.arg == 'reverse' and isinstance(kw.value, ast.Constant):
                    reverse = bool(kw.value.value)
                else:
                    self.refuse(node, 'sorted() of %s instances with %s=' % (m.name, kw.arg))
            helper = self.sort_helper(m, node)
            key = '_ail_du_sorted_r_%s' if reverse else '_ail_du_sorted_%s'
            name = self.p.helper(key % m.name, lambda name: ast.parse(
                'def %s(xs: list[%s]) -> __ail_checked_list[%s]:\n    ys = xs.copy()\n%s    %s(ys)\n%s    return ys\n'
                % (name, m.name, m.name, '    ys.reverse()\n' if reverse else '', helper,
                   '    ys.reverse()\n' if reverse else '')).body[0])
            arg = self.T(node.args[0])
            if not (isinstance(arg, tuple) and arg[0] == 'L'):
                new = self.iter_arg(node.args[0], arg)
                source = new if new is not None else self.visit(node.args[0])
            else:
                source = self.visit(node.args[0])
            self.p.changed = True
            return _locate(_call(_name(name, synth=False), [source]), node)
        # min / max of one iterable: the first best element, compared with < (min) or > (max)
        if node.keywords:
            self.refuse(node, '%s() of %s instances with keywords' % (n, m.name))
        test = self.less(m, 'x', 'best') if n == 'min' else self.greater(m, 'x', 'best')
        if test is None:
            self.refuse(node, '%s() of %s instances, which define no ordering' % (n, m.name))
        name = self.p.helper('_ail_du_%s_%s' % (n, m.name), lambda name: ast.parse(
            'def %s(xs: list[%s]) -> __ail_checked_%s__:\n'
            '    if len(xs) == 0:\n'
            '        raise ValueError("%s() iterable argument is empty")\n'
            '    best = xs[0]\n'
            '    i = 1\n'
            '    while i < len(xs):\n'
            '        x = xs[i]\n'
            '        if %s:\n'
            '            best = x\n'
            '        i += 1\n'
            '    return best\n' % (name, m.name, m.name, n, test)).body[0])
        arg = self.T(node.args[0])
        source = self.iter_arg(node.args[0], arg) if not (isinstance(arg, tuple) and arg[0] == 'L') else None
        self.p.changed = True
        return _locate(_call(_name(name, synth=False), [source if source is not None else self.visit(node.args[0])]),
                       node)

    def minmax_args(self, node, n):
        types = [self.T(a) for a in node.args]
        ms = {t[1] for t in types if inst(t)}
        if len(ms) != 1 or not all(inst(t) for t in types):
            return self.generic_visit(node)
        m = self.model(types[0])
        test = self.less(m, 'x', 'best') if n == 'min' else self.greater(m, 'x', 'best')
        if test is None:
            self.refuse(node, '%s() of %s instances, which define no ordering' % (n, m.name))
        # max(a, b, c) keeps a, takes b if b > a, then c if c > the best so far: a chain of two-way picks
        name = self.p.helper('_ail_du_%s2_%s' % (n, m.name), lambda name: ast.parse(
            'def %s(best: %s, x: %s) -> __ail_checked_%s__:\n'
            '    if %s:\n'
            '        return x\n'
            '    return best\n' % (name, m.name, m.name, m.name, test)).body[0])
        args = [self.visit(a) for a in node.args]
        best = args[0]
        for x in args[1:]:
            best = _call(_name(name, synth=False), [best, x])
        self.p.changed = True
        return _locate(best, node)


def _type_ann(t):
    if t in ('int', 'float', 'str', 'bool'):
        return ast.Name(id=t, ctx=ast.Load())
    if inst(t):
        return ast.Name(id=t[1], ctx=ast.Load())
    return None


def _fold_block(stmts):
    """Constant `if` tests left by a folded isinstance(), and the statements a return or raise makes dead."""
    out = []
    for st in stmts:
        if isinstance(st, ast.If):
            test = st.test
            value = None
            if isinstance(test, ast.Constant):
                value = bool(test.value)
            elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and isinstance(test.operand, ast.Constant):
                value = not test.operand.value
            if value is not None:
                out.extend(_fold_block(st.body if value else st.orelse))
                if out and isinstance(out[-1], (ast.Return, ast.Raise)):
                    return out
                continue
            st.body = _fold_block(st.body) or [ast.copy_location(ast.Pass(), st)]
            st.orelse = _fold_block(st.orelse)
        elif isinstance(st, (ast.For, ast.While)):
            st.body = _fold_block(st.body) or [ast.copy_location(ast.Pass(), st)]
            st.orelse = _fold_block(st.orelse)
        out.append(st)
        if isinstance(st, (ast.Return, ast.Raise)):
            return out
    return out


def _binds_deferred(st, m):
    target = st.targets[0] if isinstance(st, ast.Assign) and len(st.targets) == 1 else (
        st.target if isinstance(st, ast.AnnAssign) and st.value is not None else None)
    return isinstance(target, ast.Name) and target.id in m.deferred


def _defer(tree, models):
    assigned = set()
    for node in ast.walk(tree):
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign)) else [])
        for t in targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in models:
                    assigned.add(n.attr)
    for m in models.values():
        m.defer_constants(assigned)


def rewrite(tree, source, unsupported):
    """Lower the special methods of `tree` in place (see the module docstring); returns whether it changed."""
    reset()
    classdefs = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    if not classdefs:
        return False
    markers = _dataclass_markers(source)
    for name, info in HINT.items():
        markers.setdefault(name, info)
    models = {c.name: _Model(c, markers.get(c.name)) for c in classdefs}
    if len(models) != len(classdefs):
        return False
    _defer(tree, models)
    if not any(m.interesting() for m in models.values()):
        return False
    # a class that only is a dataclass changes nothing unless an instance is compared or shown: try it on a
    # copy first so an untouched program keeps its tree (and its C) exactly
    plain = all(not m.interesting() or (m.dataclass is not None and not (m.dunders() or m.statics or m.classmethods
                                                                         or m.props or m.attr_nodes or m.slots
                                                                         or m.total_ordering))
                for m in models.values())
    if plain:
        probe = copy.deepcopy(tree)
        pc = [n for n in probe.body if isinstance(n, ast.ClassDef)]
        pmodels = {c.name: _Model(c, markers.get(c.name)) for c in pc}
        _defer(probe, pmodels)
        p = _Pass(probe, pmodels, unsupported)
        p.run()
        if not any(m.want for m in pmodels.values()):
            reset()
            return False
        reset()
        tree.body = probe.body
        for name, m in pmodels.items():
            if m.interesting():
                ACCEPTED[name] = (m.dunders() | set(m.synth)) & METHODS
                if m.has('__bool__') or m.has('__len__'):
                    TRUTH.add(name)
        return True
    p = _Pass(tree, models, unsupported)
    changed = p.run()
    if changed and os.environ.get('AIL_DUNDERS_DUMP'):
        print(ast.unparse(tree), file=sys.stderr)
    return changed
