"""User-defined exception classes on the typed path.

    class AppError(Exception): pass
    class NotFound(AppError):
        def __init__(self, key: str, code: int = 404):
            super().__init__(f"missing {key}")
            self.key = key
            self.code = code

The typed runtime has no classes with bases, and an exception is a code, a message and arguments.  A class whose
base is a built-in exception (or another such class) and whose body is only a docstring, `pass`, constants
(`status = 404`), an `__init__` of the shape above and a `__str__` returning an expression of `self.x` is therefore
not compiled as a class: it becomes

* an exception code of its own (`Exception` is code 28, the first user class 29), with `except Base` taking
  every class derived from Base, and `str(e)`, `repr(e)`, `e.args` and `type(e).__name__` read like CPython's;
* when it has an `__init__` (its own or an inherited one), a function `_ail_new_NotFound(key, code)` that returns the
  exception (`return _ail_exc_new(30, (f"missing {key}",), 'key', key, 'code', code)`); every `NotFound(...)` call
  becomes a call of it, with the defaults and keyword arguments filled in at the call (the function has none).  A
  class with constants or a `__str__` but no `__init__` has its calls rewritten to `_ail_exc_new(...)` directly;
* its attributes, stored on the exception by index: `e.key` in a handler becomes `_ail_exc_attr_s/i/f(e, index)`;
  `__str__` is evaluated when the exception is built and kept as its text.

Attribute kinds come from annotations, defaults, constants and the kinds of the constructor calls; a parameter whose
kind cannot be told leaves the class as it was (so the program is refused with the usual "user-defined exception
class" message, or taken by the general path).  Other methods, mutable class attributes, several bases, decorators
and bases outside `ROOTS` leave the class alone for the same reason.  CPython semantics kept: `args` is what
`super().__init__` got, or the constructor arguments when there is no such call (a class that never calls
`super().__init__` still has them); instance attributes shadow class constants; a subclass without its own
`__init__` uses the inherited one.
"""
import ast

FIRST_CODE = 28            # Exception; user classes follow
EXCEPTION_NAME = 'Exception'

USER = {}                  # class name -> UserClass, in definition order
ATTRS = {}                 # attribute name -> (index, kind) with kind 's', 'i', 'f' or 'b'
NAMES = []                 # class names by code - FIRST_CODE - 1 (28 is Exception itself)


class UserClass:
    def __init__(self, name, code, base):
        self.name, self.code, self.base = name, code, base
        self.params = []           # (name, kind or None, default node or None)
        self.super_args = None     # list of expression nodes, or None when __init__ never calls super().__init__
        self.attrs = []            # (name, expression node), set in __init__
        self.class_attrs = []      # (name, constant node), set in the class body
        self.has_init = False
        self.str_expr = None       # the expression `__str__` returns (over self.attr), or None
        self.str_final = None      # ... with every self.attr replaced by the expression that sets it
        self.inline = False        # no __init__ but attributes or a __str__: calls become _ail_exc_new(...) inline
        self.node = None
        self.display = None        # the name `type(e).__name__` reads (a prelude class may keep its own identifier)

    @property
    def function(self):
        return '_ail_new_' + self.name


def final_attrs(cls):
    """The attributes an instance has: the class-body constants an __init__ store does not shadow, then the stores."""
    stored = {n for n, _ in cls.attrs}
    return [(n, e) for n, e in cls.class_attrs if n not in stored] + list(cls.attrs)


def reset():
    USER.clear()
    ATTRS.clear()
    del NAMES[:]


def reserved():
    """Codes 29..31 belong to urllib (URLError 30, HTTPError 31; 29 is spare) in a program that uses it: user classes follow."""
    import urllower
    return 3 if urllower.ACTIVE else 0


def last_code():
    return FIRST_CODE + reserved() + len(NAMES)


def derived(code):
    """Codes of the user classes derived (directly or not) from the class with this code."""
    out, todo = set(), {code}
    while todo:
        base = todo.pop()
        for c in USER.values():
            if c.base_code == base and c.code not in out:
                out.add(c.code)
                todo.add(c.code)
    return out


_KINDS = {'int': 'i', 'str': 's', 'float': 'f', 'bool': 'b'}


def _kind_of_annotation(ann):
    if isinstance(ann, ast.Name) and ann.id in _KINDS:
        return _KINDS[ann.id]
    return None


def _kind_of_constant(node):
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool):
            return 'b'
        if isinstance(v, int):
            return 'i'
        if isinstance(v, float):
            return 'f'
        if isinstance(v, str):
            return 's'
    if isinstance(node, ast.JoinedStr):
        return 's'
    return None


def _is_super_init(stmt):
    """`super().__init__(...)` as a statement; its argument list or None."""
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return None
    call = stmt.value
    f = call.func
    if not (isinstance(f, ast.Attribute) and f.attr == '__init__' and not call.keywords):
        return None
    inner = f.value
    if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == 'super' and not inner.args:
        return list(call.args)
    return None


def _is_base_init(stmt, base):
    """`Base.__init__(self, ...)` as a statement; its arguments after self, or None."""
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return None
    call = stmt.value
    f = call.func
    if (isinstance(f, ast.Attribute) and f.attr == '__init__' and isinstance(f.value, ast.Name) and f.value.id == base
            and not call.keywords and call.args and isinstance(call.args[0], ast.Name) and call.args[0].id == 'self'):
        return list(call.args[1:])
    return None


def _parse_class(node, base):
    """The shape of a candidate class, or None when it is anything else (the class is then left alone)."""
    if node.keywords or node.decorator_list or len(node.bases) != 1:
        return None
    cls = UserClass(node.name, 0, base)
    cls.node = node
    for stmt in node.body:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            continue
        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == '__ail_display_name__'
                and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)):
            cls.display = stmt.value.value
            continue
        if isinstance(stmt, ast.FunctionDef) and stmt.name == '__init__' and not cls.has_init:
            if not _parse_init(cls, stmt):
                return None
            cls.has_init = True
            continue
        if isinstance(stmt, ast.FunctionDef) and stmt.name == '__str__' and cls.str_expr is None:
            cls.str_expr = _parse_str_method(stmt)
            if cls.str_expr is None:
                return None
            continue
        target = value = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target, value = stmt.targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            target, value = stmt.target, stmt.value
        if (isinstance(target, ast.Name) and _constant_value(value) and not target.id.startswith('__')
                and all(target.id != n for n, _ in cls.class_attrs)):
            cls.class_attrs.append((target.id, value))
            continue
        return None
    return cls


def _constant_value(node):
    """A literal int, float, str or bool (a minus sign allowed)."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        node = node.operand
        return isinstance(node, ast.Constant) and type(node.value) in (int, float)
    return isinstance(node, ast.Constant) and type(node.value) in (int, float, str, bool)


def _parse_str_method(fn):
    """`def __str__(self) -> str: return <expression over self.attr>` -> the expression, or None."""
    a = fn.args
    if a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs or a.defaults or fn.decorator_list:
        return None
    if len(a.args) != 1 or a.args[0].arg != 'self':
        return None
    body = [st for st in fn.body if not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant)
                                         and isinstance(st.value.value, str))]
    if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
        return None
    for n in ast.walk(body[0].value):
        if isinstance(n, ast.Name):
            if n.id in _SAFE_CALLS or n.id in ('True', 'False', 'None'):
                continue
            if n.id == 'self':
                continue
            return None
        if isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.NamedExpr, ast.Starred)):
            return None
    for n in ast.walk(body[0].value):
        if isinstance(n, ast.Name) and n.id == 'self':
            return None if not _only_attribute_reads_of_self(body[0].value) else body[0].value
    return body[0].value


def _only_attribute_reads_of_self(expr):
    """Every `self` in `expr` is the value of an attribute read (`self.x`)."""
    ok = True

    class V(ast.NodeVisitor):
        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                return
            self.generic_visit(node)

        def visit_Name(self, node):
            nonlocal ok
            if node.id == 'self':
                ok = False

    V().visit(expr)
    return ok


def _parse_init(cls, fn):
    a = fn.args
    if a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs or fn.decorator_list:
        return False
    params = a.args
    if not params or params[0].arg != 'self':
        return False
    defaults = [None] * (len(params) - len(a.defaults)) + list(a.defaults)
    for arg, default in list(zip(params, defaults))[1:]:
        kind = _kind_of_annotation(arg.annotation) if arg.annotation is not None else None
        if arg.annotation is not None and kind is None:
            return False
        if default is not None:
            dk = _kind_of_constant(default)
            if dk is None or (kind is not None and dk != kind and not (kind == 'f' and dk == 'i')):
                return False
            kind = kind or dk
        cls.params.append((arg.arg, kind, default))
    names = {p[0] for p in cls.params}
    for stmt in fn.body:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            continue
        sup = _is_super_init(stmt)
        if sup is None:
            sup = _is_base_init(stmt, cls.base)
        if sup is not None:
            if cls.super_args is not None:
                return False                      # (two calls: not built; the order against the attribute stores does not matter)
            if not all(_plain_expr(e, names) for e in sup):
                return False
            cls.super_args = sup
            continue
        target = value = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target, value = stmt.targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            target, value = stmt.target, stmt.value
        if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self'
                and value is not None and _plain_expr(value, names)
                and all(target.attr != n for n, _ in cls.attrs)):
            cls.attrs.append((target.attr, value))
            continue
        return False
    return True


_SAFE_CALLS = {'str', 'int', 'float', 'len', 'abs', 'repr', 'bool', 'min', 'max', 'round'}


def _plain_expr(node, params):
    """An expression over the parameters, constants and a few builtins: it can move into a function of its own."""
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            if n.id in params or n.id in _SAFE_CALLS or n.id in ('True', 'False', 'None'):
                continue
            return False
        if isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.NamedExpr,
                          ast.Await, ast.Yield, ast.YieldFrom, ast.Starred)):
            return False
        if isinstance(n, ast.Attribute):
            # only a method on a value (s.upper()); self.x is not available before the attributes exist
            if isinstance(n.value, ast.Name) and n.value.id == 'self':
                return False
    return True


ROOTS = ('Exception', 'ValueError', 'ZeroDivisionError', 'IndexError', 'EOFError', 'RuntimeError', 'AssertionError',
         'OverflowError')      # built-in classes a user class may derive from (the others read their arguments differently)


def collect(tree, builtin_codes):
    """Find the user exception classes of `tree`, register them and rewrite the tree: the classes go, their
    constructor calls become calls of generated functions.  Returns True when there are any."""
    reset()
    known = {}                              # name -> UserClass or builtin name, for the base lookups
    shapes = []
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and len(node.bases) == 1 and isinstance(node.bases[0], ast.Name)):
            continue
        base = node.bases[0].id
        if node.name in builtin_codes or node.name in known:
            continue
        if base not in ROOTS and base not in known:
            continue
        cls = _parse_class(node, base)
        if cls is None:
            continue
        known[cls.name] = cls
        shapes.append(cls)
    # compose each class with the __init__ it inherits or calls, then check the attribute kinds
    good = []
    for cls in shapes:
        base = known.get(cls.base)
        if base is not None and base not in good:
            continue                         # (its base was refused)
        if not _compose(cls, base):
            continue
        if cls.has_init:
            _infer_kinds(cls, tree)
        env = {name: kind for name, kind, _ in cls.params}
        if cls.has_init and (any(kind is None for _, kind, _ in cls.params)
                             or any(_expr_kind(e, env) is None for _, e in final_attrs(cls))):
            continue                         # (a parameter of unknown kind would be taken for an int)
        if cls.str_expr is not None and not _resolve_str(cls, env):
            continue
        cls.inline = not cls.has_init and bool(final_attrs(cls) or cls.str_final is not None)
        good.append(cls)
    kinds = {}
    for cls in list(good):
        env = {name: kind for name, kind, _ in cls.params}
        for name, expr in final_attrs(cls):
            kind = _expr_kind(expr, env)
            if kinds.setdefault(name, kind) != kind:
                good.remove(cls)
                break
    # a class is dropped together with the classes derived from it
    changed = True
    while changed:
        changed = False
        for cls in list(good):
            base = known.get(cls.base)
            if base is not None and base not in good:
                good.remove(cls)
                changed = True
    if not good:
        return False
    for cls in good:
        cls.code = FIRST_CODE + 1 + reserved() + len(NAMES)
        cls.base_code = builtin_codes[cls.base] if cls.base in builtin_codes else known[cls.base].code
        NAMES.append(cls.display or cls.name)
        USER[cls.name] = cls
        for name, expr in final_attrs(cls):
            if name not in ATTRS:
                ATTRS[name] = (len(ATTRS), _expr_kind(expr, {n: k for n, k, _ in cls.params}))
    _rewrite_tree(tree)
    return True


def _infer_kinds(cls, tree):
    """A parameter without an annotation or a default that an attribute is built from: its kind is the kind the
    constructor calls give it (constants, f-strings, str()/int()/len()/float() results and names of annotated
    parameters or simply-assigned locals of the calling function), when every call agrees."""
    wanted = [i for i, (name, kind, _) in enumerate(cls.params) if kind is None]
    if not wanted:
        return
    names = [p[0] for p in cls.params]
    found = {i: set() for i in wanted}
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == cls.name):
            continue
        env = _local_kinds(node, parents)
        given = {i: a for i, a in enumerate(node.args)}
        for kw in node.keywords:
            if kw.arg in names:
                given[names.index(kw.arg)] = kw.value
        for i in wanted:
            if i in given:
                found[i].add(_expr_kind(given[i], env))
    for i in wanted:
        kinds = found[i] - {None}            # (a call whose argument is out of sight leaves it to the others)
        if len(kinds) == 1:
            name, _, default = cls.params[i]
            cls.params[i] = (name, next(iter(kinds)), default)


def _local_kinds(call, parents):
    """name -> kind for the parameters (annotated) and the plainly assigned locals of the function around `call`."""
    node = call
    while node in parents and not isinstance(node, (ast.FunctionDef, ast.Module)):
        node = parents[node]
    env = {}
    if isinstance(node, ast.FunctionDef):
        for a in node.args.args:
            k = _kind_of_annotation(a.annotation) if a.annotation is not None else None
            if k:
                env[a.arg] = k
    for n in ast.walk(node):
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            k = _kind_of_annotation(n.annotation)
            if k:
                env[n.target.id] = k
        elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            k = _expr_kind(n.value, env)
            if k and env.get(n.targets[0].id, k) == k:
                env[n.targets[0].id] = k
            elif n.targets[0].id in env and env[n.targets[0].id] != k:
                env[n.targets[0].id] = None
        elif isinstance(n, ast.For) and isinstance(n.target, ast.Name):
            env.setdefault(n.target.id, None)
    return {k: v for k, v in env.items() if v}


def _resolve_str(cls, env):
    """`__str__`'s expression with `self.x` replaced by the expression that sets x; False when it names an attribute the
    class does not set or does not come out a str."""
    import copy
    attrs = dict(final_attrs(cls))

    class Self(ast.NodeTransformer):
        failed = False

        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                if node.attr not in attrs:
                    self.failed = True
                    return node
                return copy.deepcopy(attrs[node.attr])
            return self.generic_visit(node)

    resolver = Self()
    final = resolver.visit(copy.deepcopy(cls.str_expr))
    if resolver.failed or _expr_kind(final, env) != 's':
        return False
    cls.str_final = final
    return True


class _Subst(ast.NodeTransformer):
    def __init__(self, mapping):
        self.mapping = mapping

    def visit_Name(self, node):
        if node.id in self.mapping and isinstance(node.ctx, ast.Load):
            import copy
            return copy.deepcopy(self.mapping[node.id])
        return node


def _compose(cls, base):
    """Fill in what `cls` inherits from a user class `base`, or what its own `super().__init__` hands on to it."""
    import copy
    if cls.str_expr is None and base is not None:
        cls.str_expr = base.str_expr
    if base is not None and base.class_attrs:
        own = {n for n, _ in cls.class_attrs}
        cls.class_attrs = [(n, e) for n, e in base.class_attrs if n not in own] + cls.class_attrs
    if base is None or not base.has_init:
        if cls.has_init and cls.super_args is None and any(d is not None for _, _, d in cls.params):
            return False                      # args would depend on which defaulted parameters were passed
        return True
    if not cls.has_init:
        cls.has_init = True
        cls.params = copy.deepcopy(base.params)
        cls.super_args = copy.deepcopy(base.super_args)
        cls.attrs = copy.deepcopy(base.attrs)
        return True
    if cls.super_args is None:
        if any(d is not None for _, _, d in cls.params):
            return False
        return True                           # base.__init__ never runs
    # super().__init__(x, y): base.__init__ runs with its parameters bound to the arguments
    given = cls.super_args
    if len(given) > len(base.params):
        return False
    mapping = {}
    for i, (name, kind, default) in enumerate(base.params):
        if i < len(given):
            mapping[name] = given[i]
        elif default is not None:
            mapping[name] = default
        else:
            return False
    sub = _Subst(mapping)
    base_args = base.super_args if base.super_args is not None else [ast.Name(n, ast.Load()) for n, _, _ in base.params]
    cls.super_args = [sub.visit(copy.deepcopy(e)) for e in base_args]
    inherited = [(n, sub.visit(copy.deepcopy(e))) for n, e in base.attrs]
    own = {n for n, _ in cls.attrs}
    cls.attrs = [(n, e) for n, e in inherited if n not in own] + cls.attrs
    return True


def _expr_kind(node, env):
    """The kind ('s', 'i', 'f', 'b') of a plain expression over the parameters of known kinds, or None."""
    k = _kind_of_constant(node)
    if k:
        return k
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        f = node.func.id
        if f in ('str', 'repr'):
            return 's'
        if f in ('int', 'len'):
            return 'i'
        if f == 'float':
            return 'f'
        if f == 'bool':
            return 'b'
        if f in ('abs', 'min', 'max') and node.args:
            kinds = {_expr_kind(a, env) for a in node.args}
            if kinds == {'i'}:
                return 'i'
            if None not in kinds and kinds <= {'i', 'f'}:
                return 'f'
        return None
    if isinstance(node, ast.BinOp):
        l, r = _expr_kind(node.left, env), _expr_kind(node.right, env)
        if isinstance(node.op, ast.Add) and l == r == 's':
            return 's'
        if isinstance(node.op, ast.Mult) and 's' in (l, r) and {l, r} <= {'s', 'i'}:
            return 's'
        if isinstance(node.op, ast.Div) and l in ('i', 'f') and r in ('i', 'f'):
            return 'f'
        if l in ('i', 'f') and r in ('i', 'f') and not isinstance(node.op, ast.Pow):
            return 'f' if 'f' in (l, r) else 'i'
        return None
    if isinstance(node, ast.IfExp):
        a, b = _expr_kind(node.body, env), _expr_kind(node.orelse, env)
        return a if a == b else None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _expr_kind(node.operand, env)
    return None


def _rewrite_tree(tree):
    """Drop the class definitions, add the constructor functions, turn constructor calls into calls of them."""
    drop = {c.node for c in USER.values()}
    body = [n for n in tree.body if n not in drop]
    functions = [_constructor_function(c) for c in USER.values() if c.has_init]
    # the functions go where the classes were (first class position), before anything uses them
    first = next(i for i, n in enumerate(tree.body) if n in drop)
    kept_before = [n for n in tree.body[:first] if n not in drop]
    tree.body[:] = kept_before + functions + [n for n in tree.body[first:] if n not in drop]
    init_classes = {c.name: c for c in USER.values() if c.has_init}
    inline_classes = {c.name: c for c in USER.values() if c.inline}

    class Calls(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id in init_classes:
                cls = init_classes[node.func.id]
                names = [p[0] for p in cls.params]
                given = list(node.args)
                keywords = {k.arg: k.value for k in node.keywords if k.arg}
                if (len(node.keywords) == len(keywords) and len(given) <= len(names)
                        and all(k in names[len(given):] for k in keywords)):
                    for name, kind, default in cls.params[len(given):]:
                        if name in keywords:
                            given.append(keywords[name])
                        elif default is not None:
                            given.append(default)           # (the generated function has no defaults: str ones are refused)
                        else:
                            break
                    if len(given) == len(names):
                        node.args, node.keywords = given, []
                node.func = ast.copy_location(ast.Name(cls.function, ast.Load()), node.func)
            elif isinstance(node.func, ast.Name) and node.func.id in inline_classes and not node.keywords:
                cls = inline_classes[node.func.id]
                pairs = []
                if cls.str_final is not None:
                    pairs += [ast.Constant('__str__'), cls.str_final]
                for name, expr in final_attrs(cls):
                    pairs += [ast.Constant(name), expr]
                node = ast.copy_location(ast.Call(func=ast.Name('_ail_exc_new', ast.Load()),
                                                  args=[ast.Constant(cls.code), ast.Tuple(elts=list(node.args), ctx=ast.Load())] + pairs,
                                                  keywords=[]), node)
            return node

    Calls().visit(tree)
    ast.fix_missing_locations(tree)


def _constructor_function(cls):
    params = []
    defaults = []
    for name, kind, default in cls.params:
        ann = None
        if kind:
            ann = ast.Name({'i': 'int', 's': 'str', 'f': 'float', 'b': 'bool'}[kind], ast.Load())
        params.append(ast.arg(arg=name, annotation=ann))
    args_tuple = ast.Tuple(elts=list(cls.super_args if cls.super_args is not None else [ast.Name(p[0], ast.Load()) for p in cls.params]),
                           ctx=ast.Load())
    call_args = [ast.Constant(cls.code), args_tuple]
    if cls.str_final is not None:
        call_args.append(ast.Constant('__str__'))
        call_args.append(cls.str_final)
    for name, expr in final_attrs(cls):
        call_args.append(ast.Constant(name))
        call_args.append(expr)
    ret = ast.Return(value=ast.Call(func=ast.Name('_ail_exc_new', ast.Load()), args=call_args, keywords=[]))
    fn = ast.FunctionDef(name=cls.function, args=ast.arguments(posonlyargs=[], args=params, vararg=None, kwonlyargs=[],
                                                               kw_defaults=[], kwarg=None, defaults=defaults),
                         body=[ret], decorator_list=[], returns=ast.Name('exception', ast.Load()), type_comment=None)
    return ast.copy_location(fn, cls.node)


def attr_index(name):
    return ATTRS[name]


def visible_attrs(type_node):
    """name -> (index, kind) of the attributes a handler for `type_node` may read: those of the user classes it names
    and of the classes derived from them."""
    if not USER or type_node is None:
        return {}
    names = type_node.elts if isinstance(type_node, ast.Tuple) else [type_node]
    out = {}
    for n in names:
        if isinstance(n, ast.Name) and n.id in USER:
            cls = USER[n.id]
            for c in [cls] + [USER[x] for x in USER if USER[x].code in derived(cls.code)]:
                for attr, _ in final_attrs(c):
                    out[attr] = ATTRS[attr]
    return out
