"""Spellings the typed path did not take, lowered to the forms it already builds (TYPED_BLOCKERS).

Run once on the parsed module (pyfunc `_to_c_once`), after iterlower. A program that uses none of
these spellings is not touched, so its C does not change. Each rewrite produces exactly what CPython
3.12 produces:

* `"sep".join(<generator expression>)` -> `"sep".join([<the same elements>])`. str.join turns its
  argument into a list before it reads any element (PySequence_Fast), so the elements are computed
  at the same point, in the same order, either way. Only a str literal receiver is rewritten: any
  other receiver may be an object whose own join reads a generator lazily.
* `"sep".join(reversed(X))` -> `"sep".join(X[::-1])`: X is evaluated once either way, and join
  consumes the reverse iterator completely before anything else runs, so it sees the elements of X
  back to front, which is what the slice holds. A list of str is the only X the typed path joins this way (a str, a dict
  or a list of numbers stays refused by name there).
* `"sep".join([F(e) for e in reversed(X)])` (and the generator form, and what iterlower makes of
  `map(F, reversed(X))`) -> the same comprehension over `X[::-1]` when X is a name and F and the
  conditions only read values (no call except str/int/len/abs/repr/ord/chr/min/max/float and str
  methods that return a new str), so nothing can change X while the reverse iterator walks it.
* `name = [C(...) for T in X if P]` (one `for`, the element a constructor call `C(...)`, a
  class-level call `C.make(...)` of a class of the program, or a call of a module function declared
  to return one) -> `name = []` and the loop that appends
  each element, the comprehension's names renamed so none leaks into the function (CPython scopes
  them to the comprehension). Rewritten only when the comprehension does not read `name` (it is
  bound to the new list before the loop runs) and the statement is not inside a `try` (a handler
  could see the partly built list where CPython keeps the old value).
* A constructor whose `__init__` is not only field stores, `def __init__(self, p...): LEAD;
  FIELDS; REST` (LEAD: statements that do not use `self`, such as a check that raises; FIELDS:
  `self.<name> = <expr>` stores, `self.a, self.b = x, y` included; REST: anything, with `self`
  complete), becomes `__init__` with FIELDS alone, a method `_ail_init_rest(self, p...)` with REST,
  and a module function `_ail_new_<C>(p...)` that runs LEAD, constructs, runs REST and returns the
  object; every call `C(...)` calls the function instead. The statements run in the same order with
  the same values. Done only for a class with no base that no class derives from, positional
  parameters, no `super()`, `return` or `yield` in LEAD, REST storing only fields FIELDS made,
  FIELDS and REST reading no local of LEAD but the parameters, REST not reading a parameter a field
  holds as it is (a list a field took over), and `C` used only as `C(...)`.
* `import gc` whose only uses are the statements `gc.disable()`, `gc.enable()` and `gc.collect()`:
  the import and those statements are dropped. A typed program frees memory by reference counts
  and has no cycle collector to switch, and none of the three has a value the statement uses.
"""
import ast
import copy

from iterlower import _Rename, _locate, _mark

_PURE_CALLS = frozenset(('str', 'int', 'len', 'abs', 'repr', 'ord', 'chr', 'min', 'max', 'float', 'bool'))
_PURE_METHODS = frozenset(('upper', 'lower', 'strip', 'lstrip', 'rstrip', 'zfill', 'ljust', 'rjust',
                           'center', 'replace', 'format', 'title', 'capitalize', 'swapcase', 'casefold',
                           'startswith', 'endswith', 'find', 'rfind', 'count', 'isdigit', 'isalpha',
                           'isalnum', 'isspace', 'isupper', 'islower'))


def _str_literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _pure(node, shadowed):
    """Whether evaluating `node` only reads values: no call that could run user code or mutate."""
    for each in ast.walk(node):
        if isinstance(each, (ast.NamedExpr, ast.Lambda, ast.Yield, ast.YieldFrom, ast.Await)):
            return False
        if isinstance(each, ast.Call):
            if each.keywords and not (isinstance(each.func, ast.Attribute) and each.func.attr == 'format'):
                return False
            if isinstance(each.func, ast.Name):
                if each.func.id not in _PURE_CALLS or each.func.id in shadowed:
                    return False
            elif not (isinstance(each.func, ast.Attribute) and each.func.attr in _PURE_METHODS):
                return False
    return True


def _reversed_arg(node, shadowed, name_only):
    """X for `reversed(X)` (with X a plain name when `name_only`), else None."""
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'reversed'
            and 'reversed' not in shadowed and len(node.args) == 1 and not node.keywords
            and not isinstance(node.args[0], ast.Starred)
            and (isinstance(node.args[0], ast.Name) or not name_only)):
        return node.args[0]
    return None


def _backwards(source, origin):
    step = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=1))
    sliced = ast.Subscript(value=source,
                           slice=ast.Slice(lower=None, upper=None, step=step), ctx=ast.Load())
    ast.copy_location(sliced, origin)
    ast.fix_missing_locations(sliced)
    return sliced


class _Joins(ast.NodeTransformer):
    def __init__(self, shadowed):
        self.shadowed = shadowed
        self.changed = False

    def visit_Call(self, call):
        self.generic_visit(call)
        if not (isinstance(call.func, ast.Attribute) and call.func.attr == 'join'
                and _str_literal(call.func.value) and len(call.args) == 1 and not call.keywords):
            return call
        arg = call.args[0]
        if isinstance(arg, ast.GeneratorExp):
            arg = ast.copy_location(ast.ListComp(elt=arg.elt, generators=arg.generators), arg)
            call.args = [arg]
            self.changed = True
        name = _reversed_arg(arg, self.shadowed, False)
        if name is not None:
            call.args = [_backwards(name, arg)]
            self.changed = True
            return call
        if isinstance(arg, ast.ListComp) and len(arg.generators) == 1:
            gen = arg.generators[0]
            name = _reversed_arg(gen.iter, self.shadowed, True)
            if (name is not None and not gen.is_async
                    and all(_pure(part, self.shadowed) for part in [arg.elt, *gen.ifs])
                    and not any(isinstance(n, ast.Name) and n.id == name.id
                                for n in ast.walk(gen.target))):
                gen.iter = _backwards(name, gen.iter)
                self.changed = True
        return call


def _shadowed(tree):
    """Names bound anywhere in the program (a binding of `str` or `reversed` keeps the call as written)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split('.')[0] for a in node.names)
    return names


class _ObjectComprehensions:
    def __init__(self, classes, factories):
        self.classes = classes
        self.factories = factories
        self.count = 0
        self.changed = False

    def builds_object(self, elt):
        if not isinstance(elt, ast.Call):
            return False
        func = elt.func
        if isinstance(func, ast.Name) and func.id in self.factories:
            return True
        if isinstance(func, ast.Attribute):
            func = func.value
        return isinstance(func, ast.Name) and func.id in self.classes

    def lower(self, stmt):
        """The statements for one `name = [C(...) for ...]`, or None to keep it."""
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1:
                return None
            target = stmt.targets[0]
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            target = stmt.target
        else:
            return None
        comp = stmt.value
        if not (isinstance(target, ast.Name) and isinstance(comp, ast.ListComp)
                and len(comp.generators) == 1 and not comp.generators[0].is_async
                and self.builds_object(comp.elt)):
            return None
        gen = comp.generators[0]
        inner = [comp.elt, *gen.ifs, gen.iter]
        if any(isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
                              ast.NamedExpr, ast.Yield, ast.YieldFrom, ast.Await))
               for part in inner for n in ast.walk(part)):
            return None
        if any(isinstance(n, ast.Name) and n.id == target.id for part in inner for n in ast.walk(part)):
            return None
        if not all(isinstance(n, (ast.Name, ast.Tuple, ast.Store)) for n in ast.walk(gen.target)):
            return None
        mapping = {}
        for n in ast.walk(gen.target):
            if isinstance(n, ast.Name):
                self.count += 1
                mapping[n.id] = '_ail_oc%d_%s' % (self.count, n.id)
        rename = _Rename(mapping)
        append = ast.Expr(value=ast.Call(
            func=ast.Attribute(value=ast.Name(id=target.id, ctx=ast.Load()), attr='append', ctx=ast.Load()),
            args=[_mark(rename.visit(copy.deepcopy(comp.elt)))], keywords=[]))
        body = [append]
        for condition in reversed(gen.ifs):
            body = [ast.If(test=_mark(rename.visit(copy.deepcopy(condition))), body=body, orelse=[])]
        loop = ast.For(target=_mark(rename.visit(copy.deepcopy(gen.target))), iter=gen.iter, body=body,
                       orelse=[], type_comment=None)
        empty = ast.List(elts=[], ctx=ast.Load())
        if isinstance(stmt, ast.Assign):
            head = ast.Assign(targets=[target], value=empty)
        else:
            head = ast.AnnAssign(target=target, annotation=stmt.annotation, value=empty, simple=stmt.simple)
        statements = [head, loop]
        _locate(statements, stmt)
        self.changed = True
        return statements

    def block(self, statements, in_try):
        out = []
        for stmt in statements:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                stmt.body = self.block(stmt.body, False)
                out.append(stmt)
                continue
            for field in ('body', 'orelse', 'finalbody'):
                value = getattr(stmt, field, None)
                if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
                    setattr(stmt, field, self.block(value, in_try or isinstance(stmt, ast.Try)))
            if isinstance(stmt, ast.Try):
                for handler in stmt.handlers:
                    handler.body = self.block(handler.body, True)
            lowered = None if in_try else self.lower(stmt)
            out.extend(lowered if lowered is not None else [stmt])
        return out


def _uses_self(node):
    return any(isinstance(n, ast.Name) and n.id == 'self' for n in ast.walk(node))


def _field_stores(stmt):
    """`self.a = e` -> [stmt]; `self.a, self.b = x, y` (no `self` on the right) -> one store per
    field, in order; None for any other statement."""
    if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        targets, value = [stmt.target], stmt.value
    elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        targets, value = stmt.targets, stmt.value
    else:
        return None
    target = targets[0]

    def field(t):
        return isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == 'self'
    if field(target):
        return [stmt]
    if (isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple)
            and len(target.elts) == len(value.elts) and all(field(t) for t in target.elts)
            and not any(isinstance(v, ast.Starred) for v in value.elts) and not _uses_self(value)
            and len({t.attr for t in target.elts}) == len(target.elts)):
        out = []
        for t, v in zip(target.elts, value.elts):
            out.append(ast.copy_location(ast.Assign(targets=[t], value=v), stmt))
        return out
    return None


def _bound_names(statements):
    names = set()
    for stmt in statements:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load):
                names.add(n.id)
            elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                names.add(n.name)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                names.add(n.name)
    return names


def _split_constructor(cls, tree, derived):
    """(new __init__ body, rest method or None, factory) for `cls`, or None to keep it."""
    if cls.bases or cls.keywords or cls.decorator_list or cls.name in derived:
        return None
    inits = [item for item in cls.body if isinstance(item, ast.FunctionDef) and item.name == '__init__']
    if len(inits) != 1 or inits[0].decorator_list:
        return None
    init = inits[0]
    a = init.args
    if (a.posonlyargs or a.vararg or a.kwarg or a.kwonlyargs or a.defaults or not a.args
            or a.args[0].arg != 'self'):
        return None
    params = [arg.arg for arg in a.args[1:]]
    body = [st for st in init.body
            if not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant)
                    and isinstance(st.value.value, str))]
    if any(isinstance(n, (ast.Yield, ast.YieldFrom, ast.Await, ast.Global, ast.Nonlocal))
           for st in body for n in ast.walk(st)):
        return None
    if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'super'
           for st in body for n in ast.walk(st)):
        return None
    i = 0
    while i < len(body) and not _uses_self(body[i]):
        i += 1
    lead = body[:i]
    fields = []
    while i < len(body):
        stores = _field_stores(body[i])
        if stores is None:
            break
        fields.extend(stores)
        i += 1
    rest = body[i:]
    if not fields or (not lead and not rest and len(fields) == len(body)):
        return None
    if any(isinstance(n, ast.Return) for st in lead for n in ast.walk(st)):
        return None
    if any(isinstance(n, (ast.FunctionDef, ast.Lambda, ast.ClassDef)) for st in lead for n in ast.walk(st)):
        return None
    made = {st.targets[0].attr if isinstance(st, ast.Assign) else st.target.attr for st in fields}
    for st in rest:
        for n in ast.walk(st):
            if (isinstance(n, ast.Attribute) and not isinstance(n.ctx, ast.Load)
                    and isinstance(n.value, ast.Name) and n.value.id == 'self' and n.attr not in made):
                return None
            if isinstance(n, ast.Name) and n.id == 'self' and not isinstance(n.ctx, ast.Load):
                return None
    lead_locals = _bound_names(lead) - set(params)
    later = fields + rest
    if any(isinstance(n, ast.Name) and n.id in lead_locals for st in later for n in ast.walk(st)):
        return None
    held = {st.value.id for st in fields if isinstance(st.value, ast.Name) and st.value.id in params}
    rest_reads = {n.id for st in rest for n in ast.walk(st) if isinstance(n, ast.Name)}
    if held & rest_reads:
        return None
    return lead, fields, rest, params, init


def _class_only_called(tree, name):
    """Whether every mention of class `name` outside annotations is `name(...)`."""
    annotations = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in (*n.args.posonlyargs, *n.args.args, *n.args.kwonlyargs):
                if arg.annotation is not None:
                    annotations.update(id(m) for m in ast.walk(arg.annotation))
            if n.returns is not None:
                annotations.update(id(m) for m in ast.walk(n.returns))
        elif isinstance(n, ast.AnnAssign):
            annotations.update(id(m) for m in ast.walk(n.annotation))
    calls = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id == name and id(n) not in annotations:
            if not isinstance(n.ctx, ast.Load) or id(n) not in calls:
                return False
    return True


class _CallFactory(ast.NodeTransformer):
    def __init__(self, names):
        self.names = names

    def visit_Call(self, call):
        self.generic_visit(call)
        if isinstance(call.func, ast.Name) and call.func.id in self.names:
            call.func = ast.copy_location(ast.Name(id=self.names[call.func.id], ctx=ast.Load()), call.func)
        return call


def _split_constructors(tree):
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    if not classes:
        return False
    derived = {b.id for c in ast.walk(tree) if isinstance(c, ast.ClassDef)
               for b in c.bases if isinstance(b, ast.Name)}
    taken = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    factories, inserted = {}, []
    for cls in classes:
        plan = _split_constructor(cls, tree, derived)
        if plan is None or not _class_only_called(tree, cls.name):
            continue
        lead, fields, rest, params, init = plan
        factory = '_ail_new_%s' % cls.name
        if factory in taken or '_ail_init_rest' in {i.name for i in cls.body if isinstance(i, ast.FunctionDef)}:
            continue
        init.body = fields
        args = [copy.deepcopy(arg) for arg in init.args.args[1:]]
        load = [ast.Name(id=p, ctx=ast.Load()) for p in params]
        steps = list(lead)
        steps.append(ast.Assign(targets=[ast.Name(id='_ail_obj', ctx=ast.Store())],
                                value=ast.Call(func=ast.Name(id=cls.name, ctx=ast.Load()),
                                               args=load, keywords=[])))
        if rest:
            method = ast.FunctionDef(
                name='_ail_init_rest',
                args=ast.arguments(posonlyargs=[], args=[copy.deepcopy(init.args.args[0])] + copy.deepcopy(args),
                                   vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
                body=rest, decorator_list=[], returns=ast.Name(id='__ail_checked_void__', ctx=ast.Load()),
                type_comment=None)
            ast.copy_location(method, init)
            cls.body.insert(cls.body.index(init) + 1, method)
            steps.append(ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id='_ail_obj', ctx=ast.Load()), attr='_ail_init_rest',
                                   ctx=ast.Load()),
                args=[ast.Name(id=p, ctx=ast.Load()) for p in params], keywords=[])))
        steps.append(ast.Return(value=ast.Name(id='_ail_obj', ctx=ast.Load())))
        fn = ast.FunctionDef(
            name=factory,
            args=ast.arguments(posonlyargs=[], args=args, vararg=None, kwonlyargs=[], kw_defaults=[],
                               kwarg=None, defaults=[]),
            body=steps, decorator_list=[], returns=ast.Name(id=cls.name, ctx=ast.Load()), type_comment=None)
        for node in ast.walk(fn):
            if 'lineno' in getattr(node, '_attributes', ()) and not hasattr(node, 'lineno'):
                ast.copy_location(node, init)
        factories[cls.name] = factory
        inserted.append((cls, fn))
    if not factories:
        return False
    calls = _CallFactory(factories)
    for node in tree.body:
        calls.visit(node)
    for cls, fn in inserted:
        # the statements moved into the factory call factories too; its own construction (the
        # `_ail_obj = C(...)` after them) stays the class itself
        made = next(i for i, st in enumerate(fn.body)
                    if isinstance(st, ast.Assign) and isinstance(st.targets[0], ast.Name)
                    and st.targets[0].id == '_ail_obj')
        for st in fn.body[:made]:
            calls.visit(st)
        tree.body.insert(tree.body.index(cls) + 1, fn)
    ast.fix_missing_locations(tree)
    return True


_GC_STATEMENTS = ('disable', 'enable', 'collect')


def _drop_gc(tree):
    """Drop `import gc` and its `gc.disable()` / `gc.enable()` / `gc.collect()` statements when
    those are its only uses (see the module docstring)."""
    imports = [n for n in tree.body if isinstance(n, ast.Import)
               and any(a.name == 'gc' and a.asname is None for a in n.names)]
    if not imports:
        return False
    statements = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and not n.value.args
                and not n.value.keywords and isinstance(n.value.func, ast.Attribute)
                and n.value.func.attr in _GC_STATEMENTS and isinstance(n.value.func.value, ast.Name)
                and n.value.func.value.id == 'gc'):
            statements.add(id(n.value.func.value))
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id == 'gc' and id(n) not in statements:
            return False
        if isinstance(n, ast.alias) and (n.asname == 'gc' or n.name == 'gc' and n.asname is not None):
            return False
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == 'gc':
            return False
        if isinstance(n, ast.arg) and n.arg == 'gc':
            return False
        if isinstance(n, ast.ImportFrom) and n.module == 'gc':
            return False

    class Drop(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and id(getattr(node.value.func, 'value', None)) in statements:
                return ast.copy_location(ast.Pass(), node)
            return node

    Drop().visit(tree)
    for node in imports:
        node.names = [a for a in node.names if a.name != 'gc']
        if not node.names:
            tree.body[tree.body.index(node)] = ast.copy_location(ast.Pass(), node)
    return True


def rewrite(tree):
    """Lower the spellings above in place; returns whether anything changed."""
    changed = _drop_gc(tree)
    changed = _split_constructors(tree) or changed
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    if classes and any(isinstance(n, ast.ListComp) for n in ast.walk(tree)):
        kept = classes - _shadowed_outside_classes(tree, classes)
        # module functions declared to return an instance of a class (a static method lowered by
        # dunders.py is one of these: `Point__static__parse(...) -> Point`)
        factories = {fn.name for fn in tree.body if isinstance(fn, ast.FunctionDef)
                     and _returns_class(fn.returns) in kept}
        objects = _ObjectComprehensions(kept, factories - _shadowed_outside_classes(tree, factories))
        if objects.classes:
            for fn in tree.body:
                if isinstance(fn, ast.FunctionDef):
                    fn.body = objects.block(fn.body, False)
                elif isinstance(fn, ast.ClassDef):
                    for item in fn.body:
                        if isinstance(item, ast.FunctionDef):
                            item.body = objects.block(item.body, False)
            changed = changed or objects.changed
    if not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'join'
               and _str_literal(n.func.value) for n in ast.walk(tree)):
        return changed
    joins = _Joins(_shadowed(tree))
    joins.visit(tree)
    return changed or joins.changed


def _returns_class(annotation):
    """The class name a return annotation names (`-> Point`, `-> "Point"`, or the checked spelling
    ail_syntax gives it, `-> __ail_checked_Point__`), else None."""
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return annotation.value
    if isinstance(annotation, ast.Name):
        name = annotation.id
        if name.startswith('__ail_checked_') and name.endswith('__'):
            return name[len('__ail_checked_'):-2]
        return name
    return None


def _shadowed_outside_classes(tree, classes):
    """Class names bound again somewhere (a local or a parameter of the same name)."""
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load) and node.id in classes:
            bound.add(node.id)
        elif isinstance(node, ast.arg) and node.arg in classes:
            bound.add(node.arg)
    return bound
