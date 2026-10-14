"""`bool`: the annotation, and which values print as `True`/`False`.

A bool is stored as an int64 0/1, so arithmetic, conditions and `sum(flags)` keep working exactly
as Python's bool (an int subclass) does. What a bool changes is its TEXT: `print`, `str()`, an
f-string or `.format()` field without a spec and `%s` show `True`/`False`, as CPython does; a
spec'd field (`{b:>5}`, `%d`) formats it as the int, as CPython's int.__format__ does.

`scan(tree, error)` runs once per compile, before anything else reads the annotations:

* it records every bool annotation -- parameters, results (`-> bool`, the block syntax's
  `__ail_checked_bool__`), struct fields, annotated locals, and `list[bool]` -- and rewrites it to
  the int spelling, so the rest of the compiler sees an int (list[int]) and nothing else changes;
* it infers which unannotated locals hold only bools (every assignment is a bool expression) and
  which unannotated lists hold only bools (`[False] * n`, a literal or comprehension of bools,
  with stores and appends of bools only);
* it refuses a non-bool value stored into a declared bool slot (a result, a parameter, a field,
  an annotated local, a list[bool]): Python would keep the int and print it as a number, so
  printing `True` there would be a silent mismatch. The message gives the rewrite (`x != 0`).

Before typing, a field or method is judged by name: it counts as bool when it is bool in every
struct that defines that name. The compiler's own `_is_bool_expr` uses the real receiver types
when it prints.
"""
import ast

STR_PREDICATES = frozenset(('isdigit', 'isalpha', 'isalnum', 'isspace', 'isdecimal', 'isnumeric',
                            'isupper', 'islower', 'istitle', 'startswith', 'endswith'))
SET_PREDICATES = frozenset(('issubset', 'issuperset', 'isdisjoint'))
BOOL_BUILTINS = frozenset(('bool', 'any', 'all'))


class BoolInfo:
    def __init__(self):
        self.fns = set()            # compiled names whose result is bool: 'f', 'Cls__m'
        self.list_fns = set()       # compiled names whose result is list[bool]
        self.fields = set()         # (struct, field) declared bool
        self.list_fields = set()    # (struct, field) declared list[bool]
        self.locals = {}            # compiled function name -> names holding a bool
        self.lists = {}             # compiled function name -> names holding a list of bools


EMPTY = BoolInfo()      # a program defining its own `bool` struct: nothing is a bool


def _is_bool_name(node):
    return isinstance(node, ast.Name) and node.id in ('bool', '__ail_checked_bool__')


def _is_bool_list(node):
    return (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id in ('list', '__ail_checked_list') and _is_bool_name(node.slice))


def _rewrite(ann):
    """(kind, replacement) for one annotation: kind is 'bool', 'list' or None."""
    if ann is None:
        return None, None
    if _is_bool_name(ann):
        name = '__ail_checked_int__' if ann.id == '__ail_checked_bool__' else 'int'
        return 'bool', ast.copy_location(ast.Name(id=name, ctx=ast.Load()), ann)
    if _is_bool_list(ann):
        ann.slice = ast.copy_location(ast.Name(id='int', ctx=ast.Load()), ann.slice)
        return 'list', ann
    return None, ann


class _Env:
    """What a bool expression is judged by before typing (see the module note)."""

    def __init__(self, info, classes, methods, functions):
        self.classes = classes
        self.functions = {f.name for f in functions}
        self.top_fns = {name for name in self.functions if name in info.fns}
        self.top_list_fns = {name for name in self.functions if name in info.list_fns}
        field_kinds, method_kinds, list_method_kinds = {}, {}, {}
        for cname in classes:
            init = methods[cname].get('__init__')
            if init is not None:
                for arg in init.args.args[1:]:
                    kind = ('bool' if (cname, arg.arg) in info.fields
                            else 'list' if (cname, arg.arg) in info.list_fields else 'other')
                    field_kinds.setdefault(arg.arg, set()).add(kind)
            for mname in methods[cname]:
                if mname != '__init__':
                    compiled = '%s__%s' % (cname, mname)
                    method_kinds.setdefault(mname, set()).add(compiled in info.fns)
                    list_method_kinds.setdefault(mname, set()).add(compiled in info.list_fns)
        self.bool_fields = {f for f, kinds in field_kinds.items() if kinds == {'bool'}}
        self.list_fields = {f for f, kinds in field_kinds.items() if kinds == {'list'}}
        self.bool_methods = {m for m, kinds in method_kinds.items() if kinds == {True}}
        self.list_methods = {m for m, kinds in list_method_kinds.items() if kinds == {True}}
        self.user_methods = set(method_kinds)


def boolish(node, env, names, lists):
    """True when `node` is a bool in Python, judged without types."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, bool)
    if isinstance(node, ast.Compare):
        return True
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, ast.Not)
    if isinstance(node, ast.BoolOp):
        return all(boolish(v, env, names, lists) for v in node.values)
    if isinstance(node, ast.IfExp):
        return boolish(node.body, env, names, lists) and boolish(node.orelse, env, names, lists)
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Attribute):
        return node.attr in env.bool_fields
    if isinstance(node, ast.Subscript):
        return not isinstance(node.slice, ast.Slice) and bool_list_value(node.value, env, names, lists)
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name):
            if f.id in env.functions or f.id in env.classes:
                return f.id in env.top_fns
            return f.id in BOOL_BUILTINS
        if isinstance(f, ast.Attribute):
            if f.attr in env.user_methods:
                return f.attr in env.bool_methods
            return f.attr in STR_PREDICATES or f.attr in SET_PREDICATES
    return False


def bool_list_value(node, env, names, lists):
    """True when `node` is a list whose every element is a bool."""
    if isinstance(node, ast.List):
        return bool(node.elts) and all(boolish(e, env, names, lists) for e in node.elts)
    if isinstance(node, ast.ListComp):
        return boolish(node.elt, env, names, lists)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return (bool_list_value(node.left, env, names, lists)
                or bool_list_value(node.right, env, names, lists))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return (bool_list_value(node.left, env, names, lists)
                and bool_list_value(node.right, env, names, lists))
    if isinstance(node, ast.Name):
        return node.id in lists
    if isinstance(node, ast.Attribute):
        return node.attr in env.list_fields
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        return bool_list_value(node.value, env, names, lists)
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == 'copy' and not node.args:
            return bool_list_value(f.value, env, names, lists)
        if isinstance(f, ast.Name) and f.id in ('sorted', 'list', 'reversed') and len(node.args) == 1:
            return bool_list_value(node.args[0], env, names, lists)
        if isinstance(f, ast.Name) and (f.id in env.functions or f.id in env.classes):
            return f.id in env.top_list_fns
        if isinstance(f, ast.Attribute) and f.attr in env.user_methods:
            return f.attr in env.list_methods
    return False


def _own_nodes(fn):
    """The nodes of `fn` itself (nested defs and classes excluded)."""
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                stack.append(child)


def _show(node):
    try:
        text = ast.unparse(node)
    except Exception:
        text = type(node).__name__
    return text if len(text) <= 40 else text[:37] + '...'


def _hint(value):
    return 'write a bool: True/False, a comparison, `not`, or `%s != 0`' % _show(value)


def _bound_names(target):
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def scan(tree, error):
    """Record and rewrite every bool annotation in `tree`; return a BoolInfo (see module note)."""
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    if 'bool' in classes:
        return EMPTY
    info = BoolInfo()
    methods = {cname: {m.name: m for m in cdef.body if isinstance(m, ast.FunctionDef)}
               for cname, cdef in classes.items()}
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    units = [(f.name, f, None) for f in functions]          # (compiled name, def, struct)
    for cname in classes:
        for mname, m in methods[cname].items():
            if mname != '__init__':
                units.append(('%s__%s' % (cname, mname), m, cname))
    for cname in classes:
        init = methods[cname].get('__init__')
        for arg in (init.args.args[1:] if init is not None else ()):
            kind, arg.annotation = _rewrite(arg.annotation)
            if kind == 'bool':
                info.fields.add((cname, arg.arg))
            elif kind == 'list':
                info.list_fields.add((cname, arg.arg))
    slots = {}                     # compiled name -> [(position, name, is_list)]
    declared = {}                  # compiled name -> (bool names, bool lists, annotated locals)
    for key, f, owner in units:
        names, lists, annotated = set(), set(), set()
        positional = f.args.args[1:] if owner else [*f.args.posonlyargs, *f.args.args]
        slots[key] = []
        for index, arg in enumerate([*positional, *f.args.kwonlyargs]):
            kind, arg.annotation = _rewrite(arg.annotation)
            if kind:
                (names if kind == 'bool' else lists).add(arg.arg)
                slots[key].append((index if index < len(positional) else None, arg.arg, kind == 'list'))
        kind, f.returns = _rewrite(f.returns)
        if kind == 'bool':
            info.fns.add(key)
        elif kind == 'list':
            info.list_fns.add(key)
        for node in _own_nodes(f):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                kind, node.annotation = _rewrite(node.annotation)
                if kind:
                    (names if kind == 'bool' else lists).add(node.target.id)
                    annotated.add(node.target.id)
        declared[key] = (names, lists, annotated)
    env = _Env(info, classes, methods, functions)
    for key, f, owner in units:
        fixed_names, fixed_lists, annotated = declared[key]
        params = {a.arg for a in (*f.args.posonlyargs, *f.args.args, *f.args.kwonlyargs)}
        values, loops, poisoned, breaks = {}, {}, set(), {}
        poison_at = {}
        for node in _own_nodes(f):
            if isinstance(node, ast.AugAssign):
                target = node.target.value if isinstance(node.target, ast.Subscript) else node.target
                if isinstance(target, ast.Name):
                    poison_at.setdefault(target.id, node)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension, ast.Assign)):
                for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    if isinstance(t, (ast.Tuple, ast.List)) or not isinstance(node, ast.Assign):
                        for name in _bound_names(t):
                            poison_at.setdefault(name, node.target if isinstance(node, ast.comprehension) else node)
        for node in _own_nodes(f):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    if isinstance(t, ast.Name):
                        values.setdefault(t.id, []).append(node.value)
                    elif isinstance(t, (ast.Tuple, ast.List)):
                        if (isinstance(node.value, (ast.Tuple, ast.List))
                                and len(node.value.elts) == len(t.elts)):
                            for sub, val in zip(t.elts, node.value.elts):
                                if isinstance(sub, ast.Name):
                                    values.setdefault(sub.id, []).append(val)
                                else:
                                    poisoned |= _bound_names(sub)
                        else:
                            poisoned |= _bound_names(t)
                    elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                        breaks.setdefault(t.value.id, []).append(node.value)
            elif isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name):
                    poisoned.add(node.target.id)
                    breaks.setdefault(node.target.id, []).append(None)
                elif isinstance(node.target, ast.Subscript) and isinstance(node.target.value, ast.Name):
                    breaks.setdefault(node.target.value.id, []).append(None)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                if isinstance(node.target, ast.Name):
                    loops.setdefault(node.target.id, []).append(node.iter)
                else:
                    poisoned |= _bound_names(node.target)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars is not None:
                        poisoned |= _bound_names(item.optional_vars)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                poisoned.add(node.name)
            elif isinstance(node, ast.NamedExpr):
                poisoned.add(node.target.id)
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and isinstance(node.func.value, ast.Name)):
                if node.func.attr in ('append', 'insert') and node.args:
                    breaks.setdefault(node.func.value.id, []).append(node.args[-1])
                elif node.func.attr == 'extend':
                    breaks.setdefault(node.func.value.id, []).append(
                        ('list', node.args[0] if node.args else None))
        free = (set(values) | set(loops)) - params - poisoned
        names = set(fixed_names) | (free - fixed_lists)
        lists = set(fixed_lists) | ((set(values) - params - poisoned) - fixed_names)
        changed = True
        while changed:
            changed = False
            for n in sorted(names - fixed_names):
                if not (all(boolish(v, env, names, lists) for v in values.get(n, ()))
                        and all(bool_list_value(it, env, names, lists) for it in loops.get(n, ()))):
                    names.discard(n)
                    changed = True
            for n in sorted(lists - fixed_lists):
                ok = n not in names and all(bool_list_value(v, env, names, lists)
                                            for v in values.get(n, ()))
                for brk in breaks.get(n, ()):
                    if brk is None or (isinstance(brk, tuple) and (
                            brk[1] is None or not bool_list_value(brk[1], env, names, lists))) or (
                            not isinstance(brk, tuple) and not boolish(brk, env, names, lists)):
                        ok = False
                if not ok:
                    lists.discard(n)
                    changed = True
        info.locals[key] = frozenset(names)
        info.lists[key] = frozenset(lists)
        # A declared bool slot takes only bools.
        for n in annotated & fixed_names:
            for v in values.get(n, ()):
                if not boolish(v, env, names, lists):
                    _refuse(error, '`%s`' % n, v, _hint(v))
        for n in fixed_names & params:
            for v in values.get(n, ()):
                if not boolish(v, env, names, lists):
                    _refuse(error, 'parameter `%s`' % n, v, _hint(v))
        for n in sorted(fixed_names & poisoned):
            _fail(error, '`%s` is declared bool; `+=` or a loop/unpacking target stores a number '
                  'into it -- assign a bool (True/False, a comparison, `not`)' % n, poison_at.get(n, f))
        if key in info.fns:
            for node in _own_nodes(f):
                if (isinstance(node, ast.Return) and node.value is not None
                        and not boolish(node.value, env, names, lists)):
                    _refuse(error, 'the result of %s()' % f.name, node.value,
                            'return a bool: True/False, a comparison, `not`, or `%s != 0`'
                            % _show(node.value))
        for n in fixed_lists:
            for v in values.get(n, ()):
                if not (bool_list_value(v, env, names, lists)
                        or isinstance(v, ast.List) and not v.elts):
                    _refuse(error, '`%s` (list[bool])' % n, v,
                            'build it from bools: `[False] * n`, `[x > 0 for x in xs]`')
            for brk in breaks.get(n, ()):
                if brk is None:
                    _fail(error, '`%s` is declared list[bool]; an augmented assignment stores a '
                          'number into it -- assign a bool: `%s[i] = not %s[i]`' % (n, n, n),
                          poison_at.get(n, f))
                if isinstance(brk, tuple):
                    if brk[1] is None or not bool_list_value(brk[1], env, names, lists):
                        _fail(error, '`%s` is declared list[bool]; extend it with a list of bools'
                              % n, brk[1] if brk[1] is not None else f)
                elif not boolish(brk, env, names, lists):
                    _refuse(error, 'every element of `%s`' % n, brk, _hint(brk))
        for node in _own_nodes(f):
            _check_stores(node, env, names, lists, info, classes, methods, slots, error)
    return info


def _fail(error, message, node):
    """Raise `error(message)` located at `node` (the compiler maps the line to `file:line:col`)."""
    exc = error(message)
    if getattr(node, 'lineno', None) is not None:
        exc.source_line = node.lineno
    raise exc


def _refuse(error, what, value, rewrite):
    _fail(error, '%s is declared bool, but `%s` is not a bool (Python would keep the number and '
          'print it as one); %s' % (what, _show(value), rewrite), value)


def _check_stores(node, env, names, lists, info, classes, methods, slots, error):
    """Field stores, constructor arguments and call arguments into declared bool slots."""
    if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
        for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
            if (isinstance(t, ast.Attribute) and t.attr in env.bool_fields
                    and not boolish(node.value, env, names, lists)):
                _refuse(error, 'field `%s`' % t.attr, node.value, _hint(node.value))
            if (isinstance(t, ast.Attribute) and t.attr in env.list_fields
                    and not bool_list_value(node.value, env, names, lists)
                    and not (isinstance(node.value, ast.List) and not node.value.elts)):
                _refuse(error, 'field `%s` (list[bool])' % t.attr, node.value,
                        'assign a list of bools (`[False] * n`)')
            if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute)
                    and t.value.attr in env.list_fields and not boolish(node.value, env, names, lists)):
                _refuse(error, 'every element of field `%s`' % t.value.attr, node.value,
                        _hint(node.value))
    if isinstance(node, ast.AugAssign):
        target = node.target.value if isinstance(node.target, ast.Subscript) else node.target
        if isinstance(target, ast.Attribute) and (
                target.attr in env.bool_fields and target is node.target
                or target.attr in env.list_fields and target is not node.target):
            _fail(error, 'field `%s` is declared bool; `%s` stores a number -- assign a bool '
                  '(`not ...`, a comparison)' % (target.attr, _show(node)), node)
    if not isinstance(node, ast.Call):
        return
    f = node.func
    if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Attribute)
            and f.value.attr in env.list_fields and f.attr in ('append', 'insert') and node.args
            and not boolish(node.args[-1], env, names, lists)):
        _refuse(error, 'every element of field `%s`' % f.value.attr, node.args[-1],
                _hint(node.args[-1]))
    wanted, what = None, None
    if isinstance(f, ast.Name) and f.id in classes:
        init = methods[f.id].get('__init__')
        if init is None:
            return
        wanted = [(i, a.arg, (f.id, a.arg) in info.list_fields)
                  for i, a in enumerate(init.args.args[1:])
                  if (f.id, a.arg) in info.fields or (f.id, a.arg) in info.list_fields]
        what = lambda name: 'field %s.%s' % (f.id, name)
    elif isinstance(f, ast.Name) and f.id in env.functions:
        wanted = slots.get(f.id)
        what = lambda name: 'parameter `%s` of %s()' % (name, f.id)
    elif isinstance(f, ast.Attribute):
        owners = [c for c in classes if f.attr in methods[c]]
        if len(owners) == 1:
            wanted = slots.get('%s__%s' % (owners[0], f.attr))
            what = lambda name: 'parameter `%s` of %s.%s()' % (name, owners[0], f.attr)
    for index, name, is_list in wanted or ():
        value = (node.args[index] if index is not None and index < len(node.args)
                 else next((k.value for k in node.keywords if k.arg == name), None))
        if value is None:
            continue
        if is_list:
            if not bool_list_value(value, env, names, lists) and not (
                    isinstance(value, ast.List) and not value.elts):
                _refuse(error, what(name) + ' (list[bool])', value,
                        'pass a list of bools (`[False] * n`, a list[bool] local)')
        elif not boolish(value, env, names, lists):
            _refuse(error, what(name), value, _hint(value))
