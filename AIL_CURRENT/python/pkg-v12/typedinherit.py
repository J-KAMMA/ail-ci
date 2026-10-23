"""Single inheritance on the typed path: the source-level half (docs/design/TYPED_INHERITANCE.md).

`pyfunc._scan_classes` calls these on the class definitions before any body is compiled:

* `class_base` names the one base class of a `class D(B):` (or None), refusing by name every base that
  is not a class of this program and every second base;
* `expand_init` returns `D.__init__` with each `super().__init__(...)` / `B.__init__(self, ...)` replaced
  by the base's own `self.f = ...` stores, its parameters bound to the call's arguments (a subclass
  without `__init__` gets its base's);
* `rewrite_super_calls` turns `super().m(...)` / `B.m(self, ...)` in a method into a direct call of the
  method `B` resolves `m` to, under its compiled name;
* `class_attributes` reads the `K = <literal>` statements of a class body;
* `narrow_isinstance` gives `if isinstance(x, C):` a local of class C for x inside the branch.

Nothing here runs for a program without a base class or a class attribute.
"""
import ast
import copy

# Bases that are some library's class, not a class of the program: named in the refusal.
_FOREIGN_HINTS = {
    'Enum': 'an Enum (write the members as module constants, `RED = 0`)',
    'IntEnum': 'an IntEnum (write the members as module constants, `RED = 0`)',
    'NamedTuple': 'a NamedTuple (write a class with an __init__)',
    'ABC': 'abc.ABC (drop the base; a method every subclass overrides needs no marker)',
    'Generic': 'typing.Generic (drop the type parameter)',
    'Protocol': 'typing.Protocol (drop the base)',
}


def _refusal(Unsupported, node, message):
    refusal = Unsupported(message)
    refusal.source_line = getattr(node, 'lineno', None)
    return refusal


def class_base(c, known, Unsupported):
    """The name of the one base class of `c` among `known` (classes defined earlier in the source), or
    None for no base or `object`. Everything else is refused by name."""
    if c.keywords:
        raise _refusal(Unsupported, c, 'class %r passes a keyword in its bases (%s); a class here takes '
                       'one base class of this program and nothing else'
                       % (c.name, ', '.join('%s=' % k.arg for k in c.keywords)))
    bases = [b for b in c.bases if not (isinstance(b, ast.Name) and b.id == 'object')]
    if not bases:
        return None
    if len(bases) > 1:
        raise _refusal(Unsupported, c, 'multiple inheritance (class %r names %d bases: %s); a class here '
                       'has at most one base class.\n'
                       '  write instead: one base class, and hold the other as a field (`self.part = Part(...)`)'
                       % (c.name, len(bases), ', '.join(ast.unparse(b) for b in bases)))
    base = bases[0]
    name = base.id if isinstance(base, ast.Name) else None
    if name is not None and name.endswith(('Error', 'Exception')) and name not in known:
        raise _refusal(Unsupported, c,
                       'inheritance (class %r names a base class); a user-defined exception class is '
                       'not built here.\n'
                       '  write instead: raise a built-in exception (`raise ValueError("negative")`) '
                       'and catch it by that name (`except ValueError:`)' % c.name)
    if name is not None and name in known:
        return name
    what = _FOREIGN_HINTS.get(name if name is not None else
                              base.value.id if isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name)
                              else '', None)
    raise _refusal(Unsupported, c,
                   'inheritance from %s (class %r); a class here may only derive from a class defined '
                   'earlier in this program.\n'
                   '  write instead: %s' % (repr(ast.unparse(base)), c.name,
                                            what or 'a standalone class that holds the other as a field '
                                            '(`self.base = Base(...)`)'))


def is_stub(fn):
    """A method whose body does nothing: `...`, `pass`, a docstring, or `raise NotImplementedError`."""
    body = [s for s in fn.body
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))]
    if not body:
        return True
    if len(body) != 1:
        return False
    s = body[0]
    if isinstance(s, ast.Pass) or isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and s.value.value is Ellipsis:
        return True
    if isinstance(s, ast.Raise) and s.exc is not None:
        e = s.exc.func if isinstance(s.exc, ast.Call) else s.exc
        return isinstance(e, ast.Name) and e.id == 'NotImplementedError'
    return False


def _is_super_call(call, cname, attr=None):
    """`super().attr(...)`, `super(C, self).attr(...)`: the attribute name, else None."""
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
        return None
    s = call.func.value
    if not (isinstance(s, ast.Call) and isinstance(s.func, ast.Name) and s.func.id == 'super' and not s.keywords):
        return None
    if s.args and not (len(s.args) == 2 and isinstance(s.args[0], ast.Name) and s.args[0].id == cname
                       and isinstance(s.args[1], ast.Name) and s.args[1].id == 'self'):
        return None
    return call.func.attr if attr is None or call.func.attr == attr else None


def _is_named_base_call(call, base_chain, attr=None):
    """`B.attr(self, ...)` where B is the class's base or one of its ancestors: (B, attr), else None."""
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name) and call.func.value.id in base_chain
            and call.args and isinstance(call.args[0], ast.Name) and call.args[0].id == 'self'):
        return None
    if attr is not None and call.func.attr != attr:
        return None
    return call.func.value.id, call.func.attr


_PURE_NODES = (ast.Name, ast.Constant, ast.UnaryOp, ast.BinOp, ast.BoolOp, ast.Compare, ast.IfExp,
               ast.Load, ast.operator, ast.unaryop, ast.boolop, ast.cmpop)


def _pure_argument(node):
    """Re-evaluating this argument (or not evaluating it) gives the same result: names (parameters,
    which `__init__` never rebinds), constants and arithmetic on them, nothing that calls or reads a field."""
    return all(isinstance(n, _PURE_NODES) for n in ast.walk(node))


def _bind(params, call_args, call_keywords, cname, bname, node, Unsupported):
    names = [a.arg for a in params]
    if len(call_args) > len(names):
        raise _refusal(Unsupported, node, '%s.__init__() takes %d arguments (from %s.__init__)'
                       % (bname, len(names), cname))
    bound = dict(zip(names, call_args))
    for kw in call_keywords:
        if kw.arg is None or kw.arg not in names or kw.arg in bound:
            raise _refusal(Unsupported, node, '%s.__init__() has no argument %r to bind (from %s.__init__)'
                           % (bname, kw.arg, cname))
        bound[kw.arg] = kw.value
    missing = [n for n in names if n not in bound]
    if missing:
        raise _refusal(Unsupported, node, '%s.__init__() is missing argument %r (from %s.__init__)'
                       % (bname, missing[0], cname))
    for value in bound.values():
        if isinstance(value, (ast.Starred,)):
            raise _refusal(Unsupported, node, 'super().__init__(*args) is not built; pass the arguments by name')
    return bound


class _Substitute(ast.NodeTransformer):
    def __init__(self, bound):
        self.bound = bound

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.bound:
            return ast.copy_location(copy.deepcopy(self.bound[node.id]), node)
        return node


def _inline_base_init(call, base_init, cname, bname, own_params, Unsupported):
    """The base's (already expanded) `__init__` statements for one `super().__init__(...)` call."""
    params = base_init.args.args[1:]
    args = call.args[1:] if _is_named_base_call(call, {bname}) else call.args
    bound = _bind(params, args, call.keywords, cname, bname, call, Unsupported)
    uses = {}
    free = set()
    for stmt in base_init.body:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                if n.id in bound:
                    uses[n.id] = uses.get(n.id, 0) + 1
                elif n.id != 'self':
                    free.add(n.id)
    clash = free & own_params
    if clash:
        raise _refusal(Unsupported, call, '%s.__init__ has a parameter %r, a name %s.__init__ also uses; '
                       'rename the parameter' % (cname, sorted(clash)[0], bname))
    for name, value in bound.items():
        if not _pure_argument(value):
            raise _refusal(Unsupported, call,
                           'super().__init__(...) argument %r for %s.%s is not a name, a constant or '
                           'arithmetic on them.\n'
                           '  write instead: make it a parameter of %s.__init__, or compute it in the '
                           'caller' % (ast.unparse(value), bname, name, cname))
    out = []
    for stmt in base_init.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            continue
        new = _Substitute(bound).visit(copy.deepcopy(stmt))
        out.append(ast.copy_location(new, call))
    return out


def _super_init_stmt(stmt, cname, base_chain):
    """Whether `stmt` is `super().__init__(...)` or `B.__init__(self, ...)` (B the base), as a statement."""
    if not isinstance(stmt, ast.Expr):
        return None
    call = stmt.value
    if _is_super_call(call, cname, '__init__'):
        return call
    hit = _is_named_base_call(call, base_chain[:1], '__init__')
    return call if hit else None


def expand_init(c, init_fn, base_name, base_init, base_fields, base_chain, Unsupported):
    """`c.__init__` with its base's construction inlined. `init_fn` is the class's own `__init__` or None,
    `base_init` the base's expanded `__init__` (None for a base without fields). Returns the new
    FunctionDef."""
    if init_fn is None:
        if base_init is None:
            fn = ast.FunctionDef(name='__init__', args=ast.arguments(
                posonlyargs=[], args=[ast.arg(arg='self')], vararg=None, kwonlyargs=[], kw_defaults=[],
                kwarg=None, defaults=[]), body=[], decorator_list=[], returns=None)
            return ast.fix_missing_locations(ast.copy_location(fn, c))
        fn = copy.deepcopy(base_init)
        fn.lineno = c.lineno
        return fn
    fn = copy.deepcopy(init_fn)
    own_params = {a.arg for a in fn.args.args[1:]}
    body, called = [], False
    for stmt in fn.body:
        call = _super_init_stmt(stmt, c.name, base_chain)
        if call is None:
            for n in ast.walk(stmt):
                if _is_super_call(n, c.name) or _is_named_base_call(n, base_chain):
                    raise _refusal(Unsupported, n, 'super() in %s.__init__ other than the statement '
                                   '`super().__init__(...)`' % c.name)
            body.append(stmt)
            continue
        called = True
        if base_init is not None:
            body.extend(_inline_base_init(call, base_init, c.name, base_name, own_params, Unsupported))
        elif call.args[1 if _is_named_base_call(call, base_chain[:1]) else 0:] or call.keywords:
            raise _refusal(Unsupported, call, '%s.__init__() takes no arguments (from %s.__init__)'
                           % (base_name, c.name))
    if not called and base_fields:
        assigned = {s.targets[0].attr for s in body if isinstance(s, ast.Assign)
                    and isinstance(s.targets[0], ast.Attribute)}
        assigned |= {s.target.attr for s in body if isinstance(s, ast.AnnAssign)
                     and isinstance(s.target, ast.Attribute)}
        missing = [f for f in base_fields if f not in assigned]
        if missing:
            raise _refusal(Unsupported, init_fn,
                           '%s.__init__ does not call super().__init__(...), so field %r of %s is never '
                           'set (CPython raises AttributeError when it is read).\n'
                           '  write instead: call `super().__init__(...)` in %s.__init__'
                           % (c.name, missing[0], base_name, c.name))
    assigned = set()
    for stmt in body:
        value = getattr(stmt, 'value', None)
        for n in ast.walk(value) if value is not None else ():
            if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == 'self'
                    and n.attr in base_fields and n.attr not in assigned):
                raise _refusal(Unsupported, n, '%s.__init__ reads self.%s before super().__init__(...) sets it '
                               '(CPython raises AttributeError).\n'
                               '  write instead: call super().__init__(...) first' % (c.name, n.attr))
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target] if isinstance(stmt, ast.AnnAssign) else []
        assigned.update(t.attr for t in targets if isinstance(t, ast.Attribute))
    fn.body = body
    return fn


class _SuperCalls(ast.NodeTransformer):
    def __init__(self, cname, base_chain, resolve, Unsupported):
        self.cname, self.base_chain, self.resolve, self.Unsupported = cname, base_chain, resolve, Unsupported

    def visit_Call(self, node):
        attr = _is_super_call(node, self.cname)
        if attr is not None:
            node.args = [self.visit(a) for a in node.args]
            for kw in node.keywords:
                kw.value = self.visit(kw.value)
        else:
            self.generic_visit(node)
        start = self.base_chain[0] if self.base_chain else None
        args = node.args
        if attr is None:
            hit = _is_named_base_call(node, self.base_chain)
            if hit is None:
                return node
            start, attr = hit
            args = node.args[1:]
        if attr == '__init__':
            raise _refusal(self.Unsupported, node, '%s.__init__ called from a method of %s; only '
                           '%s.__init__ may call it' % (start, self.cname, self.cname))
        target = self.resolve(start, attr) if start is not None else None
        if target is None:
            raise _refusal(self.Unsupported, node, 'super().%s(): no base class of %s defines %s'
                           % (attr, self.cname, attr))
        call = ast.Call(func=ast.Name(id=target, ctx=ast.Load()), args=[ast.Name(id='self', ctx=ast.Load())] + args,
                        keywords=node.keywords)
        return ast.copy_location(call, node)

    def visit_Name(self, node):
        if node.id == 'super':
            raise _refusal(self.Unsupported, node, 'super() other than `super().method(...)` in a method of %s'
                           % self.cname)
        return node


def rewrite_super_calls(fn, cname, base_chain, resolve, Unsupported):
    """`super().m(a)` / `B.m(self, a)` in method `fn` of class `cname` -> `<compiled name>(self, a)`."""
    if not any(isinstance(n, ast.Name) and (n.id == 'super' or n.id in base_chain) for n in ast.walk(fn)):
        return fn
    out = _SuperCalls(cname, base_chain, resolve, Unsupported).visit(fn)
    ast.fix_missing_locations(out)
    return out


def class_attribute(stmt):
    """(name, value) for a class-body `K = literal` / `K: T = literal`, else None."""
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        return stmt.targets[0].id, stmt.value
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
        return stmt.target.id, stmt.value
    return None


def literal_kind(value):
    """'int', 'float', 'str' or 'bool' for a literal class attribute value (a negative number too), else None."""
    v = value
    if isinstance(v, ast.UnaryOp) and isinstance(v.op, (ast.USub, ast.UAdd)) and isinstance(v.operand, ast.Constant):
        v = v.operand
        if type(v.value) not in (int, float):
            return None
    if not isinstance(v, ast.Constant):
        return None
    return {bool: 'bool', int: 'int', float: 'float', str: 'str'}.get(type(v.value))


_ANNOTATION = {'int': 'int', 'float': 'float', 'str': 'str', 'bool': 'bool'}


def _attr_getter(name, value, kind, at):
    fn = ast.FunctionDef(name=getter_name(name), args=ast.arguments(
        posonlyargs=[], args=[ast.arg(arg='self')], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None,
        defaults=[]), body=[ast.Return(value=copy.deepcopy(value))], decorator_list=[],
        returns=ast.Name(id=_ANNOTATION[kind], ctx=ast.Load()))
    ast.copy_location(fn, at)
    return ast.fix_missing_locations(fn)


def getter_name(attr):
    return '_ail_ca_' + attr


def _class_name_read(node):
    """The instance of `type(x).__name__` / `x.__class__.__name__`, else None."""
    if not (isinstance(node, ast.Attribute) and node.attr == '__name__' and isinstance(node.ctx, ast.Load)):
        return None
    v = node.value
    if (isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == 'type' and len(v.args) == 1
            and not v.keywords):
        return v.args[0]
    if isinstance(v, ast.Attribute) and v.attr == '__class__':
        return v.value
    return None


def lower_class_names(tree):
    """`type(x).__name__` (and `x.__class__.__name__`) for an instance of a class of the program: a
    method `_ail_classname` that each class defines to return its own name, so the run-time class's
    is read. A no-op for a program that never asks."""
    if not any(_class_name_read(n) is not None for n in ast.walk(tree)):
        return
    for c in tree.body:
        if isinstance(c, ast.ClassDef):
            # the tuple pass's record classes are tuples to CPython (`type((1, 2)).__name__`)
            name = 'tuple' if c.name.startswith('_AilT_') else c.name
            c.body.append(_attr_getter('_ail_classname', ast.Constant(value=name), 'str', c))
            c.body[-1].name = '_ail_classname'

    class Reads(ast.NodeTransformer):
        def visit_Attribute(self, node):
            self.generic_visit(node)
            target = _class_name_read(node)
            if target is None:
                return node
            return ast.copy_location(ast.Call(func=ast.Attribute(value=target, attr='_ail_classname', ctx=ast.Load()),
                                              args=[], keywords=[]), node)
    Reads().visit(tree)
    ast.fix_missing_locations(tree)


def lower_class_attributes(tree, Unsupported):
    """Class attributes (`K = <literal>` in a class body) become methods: `x.K` reads `x._ail_ca_K()`, so
    a subclass inherits or redefines them exactly as it does a method, and `C.K` is the literal C
    resolves it to. A no-op for a program whose classes have none."""
    classdefs = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    attrs = {}
    for c in classdefs:
        for stmt in c.body:
            got = class_attribute(stmt)
            if got is not None:
                name, value = got
                kind = literal_kind(value)
                if kind is None:
                    raise _refusal(Unsupported, stmt,
                                   'class attribute %s.%s = %s; a class attribute here is an int, float, str or '
                                   'bool literal.\n'
                                   '  write instead: a module-level constant, or set the value in __init__ '
                                   '(`self.%s = ...`)' % (c.name, name, ast.unparse(value), name))
                attrs.setdefault(c.name, {})[name] = (kind, value, stmt)
    if not attrs:
        return
    names = {n for table in attrs.values() for n in table}
    fields = set()
    for node in ast.walk(tree):
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign)) else [])
        for t in targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Attribute) and n.attr in names:
                    if isinstance(n.value, ast.Name) and n.value.id in attrs:
                        raise _refusal(Unsupported, n, 'assigning the class attribute %s.%s; a class '
                                       'attribute here is a constant' % (n.value.id, n.attr))
                    fields.add(n.attr)
    clash = names & fields
    if clash:
        name = sorted(clash)[0]
        owner = sorted(k for k in attrs if name in attrs[k])[0]
        raise _refusal(Unsupported, attrs[owner][name][2],
                       '%s is a class attribute of %s and is also assigned through an instance '
                       '(`x.%s = ...`); a class attribute here is a constant, and a field has another name'
                       % (name, owner, name))
    bases = {c.name: (c.bases[0].id if len(c.bases) == 1 and isinstance(c.bases[0], ast.Name) else None)
             for c in classdefs}
    for c in classdefs:
        for name, (kind, value, stmt) in attrs.get(c.name, {}).items():
            if any(isinstance(m, ast.FunctionDef) and m.name in (name, getter_name(name)) for m in c.body):
                raise _refusal(Unsupported, stmt, '%s.%s is a class attribute and a method' % (c.name, name))

    def resolve(cls, name):
        while cls is not None and cls in bases:
            if name in attrs.get(cls, {}):
                return attrs[cls][name]
            cls = bases[cls]
        return None
    for c in classdefs:
        for name, (kind, value, stmt) in attrs.get(c.name, {}).items():
            above = resolve(bases[c.name], name)
            if above is not None and above[0] != kind:
                raise _refusal(Unsupported, stmt, '%s.%s is %s and the %s it redefines is %s; a class attribute '
                               'keeps its type in a subclass' % (c.name, name, kind, name, above[0]))
        c.body = [(_attr_getter(class_attribute(s)[0], class_attribute(s)[1],
                                attrs[c.name][class_attribute(s)[0]][0], s) if class_attribute(s) else s)
                  for s in c.body]

    modules = {(a.asname or a.name).split('.')[0] for n in ast.walk(tree)
               if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}

    class Reads(ast.NodeTransformer):
        def visit_Attribute(self, node):
            self.generic_visit(node)
            if (node.attr not in names or not isinstance(node.ctx, ast.Load)
                    or isinstance(node.value, ast.Name) and node.value.id in modules - set(bases)):
                return node
            if isinstance(node.value, ast.Name) and node.value.id in bases:
                got = resolve(node.value.id, node.attr)
                if got is None:
                    raise _refusal(Unsupported, node, 'class %s has no class attribute %s'
                                   % (node.value.id, node.attr))
                return ast.copy_location(copy.deepcopy(got[1]), node)
            call = ast.Call(func=ast.Attribute(value=node.value, attr=getter_name(node.attr), ctx=ast.Load()),
                            args=[], keywords=[])
            return ast.copy_location(call, node)
    Reads().visit(tree)
    ast.fix_missing_locations(tree)


class _Narrow(ast.NodeTransformer):
    """Inside `if isinstance(x, C):`, read `x` through a new local of class C."""
    def __init__(self, hier):
        self.hier = hier
        self.count = 0

    def _test(self, t):
        """(x, C) for `isinstance(x, C)` with x a name and C a class of a hierarchy, else None."""
        if (isinstance(t, ast.Call) and isinstance(t.func, ast.Name) and t.func.id == 'isinstance'
                and len(t.args) == 2 and not t.keywords and isinstance(t.args[0], ast.Name)
                and isinstance(t.args[1], ast.Name) and t.args[1].id in self.hier):
            return t.args[0].id, t.args[1].id
        return None

    def visit_If(self, node):
        t = node.test
        if (isinstance(t, ast.BoolOp) and isinstance(t.op, ast.And) and self._test(t.values[0]) is not None
                and sum(1 for s in node.orelse for _ in ast.walk(s)) <= 300):
            # `if isinstance(x, C) and rest: body else: other` is
            # `if isinstance(x, C): (if rest: body else: other) else: other`
            rest = t.values[1:]
            inner = ast.If(test=rest[0] if len(rest) == 1 else ast.BoolOp(op=ast.And(), values=rest),
                           body=node.body, orelse=copy.deepcopy(node.orelse))
            ast.copy_location(inner, node)
            node.test, node.body = t.values[0], [inner]
        self.generic_visit(node)
        test = self._test(node.test)
        if test is None:
            return node
        name, cls = test
        if name == 'self' or not any(isinstance(n, ast.Name) and n.id == name
                                     for stmt in node.body for n in ast.walk(stmt)):
            return node
        for stmt in node.body:
            for n in ast.walk(stmt):
                if (isinstance(n, ast.Name) and n.id == name and not isinstance(n.ctx, ast.Load)
                        or isinstance(n, (ast.FunctionDef, ast.Lambda, ast.ClassDef, ast.Global, ast.Nonlocal))
                        or isinstance(n, ast.NamedExpr)):
                    return node
        self.count += 1
        alias = '_ail_narrow%d_%s' % (self.count, name)

        class Rename(ast.NodeTransformer):
            def visit_Name(self, n):
                if n.id == name:
                    return ast.copy_location(ast.Name(id=alias, ctx=n.ctx), n)
                return n
        body = [Rename().visit(s) for s in node.body]
        bind = ast.AnnAssign(target=ast.Name(id=alias, ctx=ast.Store()), annotation=ast.Name(id=cls, ctx=ast.Load()),
                             value=ast.Name(id=name, ctx=ast.Load()), simple=1)
        bind._ail_narrow = True
        ast.copy_location(bind, node)
        node.body = [bind] + body
        return node


def narrow_isinstance(fn, hier):
    """Rewrite every `if isinstance(x, C):` branch of `fn` that does not rebind x (C a class of a hierarchy)."""
    if not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'isinstance'
               for n in ast.walk(fn)):
        return
    _Narrow(hier).visit(fn)
    ast.fix_missing_locations(fn)
