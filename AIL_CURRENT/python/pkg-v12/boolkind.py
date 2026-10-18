"""`bool`: the annotation, and which values print as `True`/`False`.

A bool is stored as an int64 0/1, so arithmetic, conditions and `sum(flags)` keep working exactly
as Python's bool (an int subclass) does. What a bool changes is its TEXT: `print`, `str()`, an
f-string or `.format()` field without a spec and `%s` show `True`/`False`, as CPython does; a
spec'd field (`{b:>5}`, `%d`) formats it as the int, as CPython's int.__format__ does.

`scan(tree, error)` runs once per compile, before anything else reads the annotations:

* it records every bool annotation -- parameters, results (`-> bool`, the block syntax's
  `__ail_checked_bool__`), struct fields (an `__init__` parameter or `self.f: bool = ...`), annotated
  locals, `list[bool]` and `dict[K, bool]` -- and rewrites it to the int spelling, so the rest of the
  compiler sees an int (list[int], dict[K, int]) and nothing else changes;
* it infers which unannotated things hold only bools, to a fixed point over the whole program:
  locals (every assignment is a bool expression), lists and dicts of bools (a literal or
  comprehension of bools, with stores and appends of bools only), results, parameters of functions,
  methods and constructors (every call passes a bool), and FIELDS (every store to the name, in
  `__init__` or anywhere, is a bool: `self.done = True` makes `done` a bool field);
* it refuses a non-bool value stored into a declared bool slot (a result, a parameter, a field,
  an annotated local, a list[bool]): Python would keep the int and print it as a number, so
  printing `True` there would be a silent mismatch. The message gives the rewrite (`x != 0`);
* it refuses the same mismatch from the other side, where one slot would hold a bool in some places
  and a number in others (a field, a result, a list or dict, a ternary, a `max` of both, a list
  literal), or where a bool goes into a slot declared int: an int64 cannot tell them apart, CPython
  prints them differently (True / 1). The general path runs those programs.

A bool container is a list or a dict whose elements (values) are all bools. Its name is in the
`lists` set; a dict also has the marker `'{}' + name` there, so that iterating it (which yields
keys) is not mistaken for iterating its values.

Before typing, a field or method is judged by name: it counts as bool when it is bool in every
struct that defines that name. The compiler's own `_is_bool_expr` uses the real receiver types
when it prints, through the same `boolish` with a different environment.
"""
import ast
import os

STR_PREDICATES = frozenset(('isdigit', 'isalpha', 'isalnum', 'isspace', 'isdecimal', 'isnumeric',
                            'isupper', 'islower', 'istitle', 'startswith', 'endswith'))
SET_PREDICATES = frozenset(('issubset', 'issuperset', 'isdisjoint'))
BOOL_BUILTINS = frozenset(('bool', 'any', 'all', 'isinstance'))
TEXT_CALLS = frozenset(('print', 'str', 'repr', 'format', 'ascii'))
INT_NAMES = frozenset(('int', '__ail_checked_int__'))


class BoolInfo:
    def __init__(self):
        self.fns = set()            # compiled names whose result is bool: 'f', 'Cls__m'
        self.list_fns = set()       # compiled names whose result is a bool list or dict
        self.dict_fns = set()       # ... of those, the ones that return a dict
        self.fields = set()         # (struct, field) holding a bool
        self.list_fields = set()    # (struct, field) holding a list or dict of bools
        self.dict_fields = set()    # ... of those, the dicts
        self.locals = {}            # compiled function name -> names holding a bool
        self.lists = {}             # compiled function name -> names holding a bool list or dict
        self.env = None             # what `boolish` judges by (set by `scan`)
        self.units = ()             # [(compiled name, def)] of every function `scan` looked at


EMPTY = BoolInfo()      # a program defining its own `bool` struct: nothing is a bool


def _is_bool_name(node):
    return isinstance(node, ast.Name) and node.id in ('bool', '__ail_checked_bool__')


def _is_bool_list(node):
    return (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id in ('list', '__ail_checked_list') and _is_bool_name(node.slice))


def _is_bool_dict(node):
    return (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id in ('dict', '__ail_checked_dict') and isinstance(node.slice, ast.Tuple)
            and len(node.slice.elts) == 2 and _is_bool_name(node.slice.elts[1]))


def _rewrite(ann):
    """(kind, replacement) for one annotation: kind is 'bool', 'list', 'dict' or None."""
    if ann is None:
        return None, None
    if _is_bool_name(ann):
        name = '__ail_checked_int__' if ann.id == '__ail_checked_bool__' else 'int'
        return 'bool', ast.copy_location(ast.Name(id=name, ctx=ast.Load()), ann)
    if _is_bool_list(ann):
        ann.slice = ast.copy_location(ast.Name(id='int', ctx=ast.Load()), ann.slice)
        return 'list', ann
    if _is_bool_dict(ann):
        ann.slice.elts[1] = ast.copy_location(ast.Name(id='int', ctx=ast.Load()), ann.slice.elts[1])
        return 'dict', ann
    return None, ann


def _python_surface():
    """The refusals of a slot that mixes bools and numbers keep CPython's output; they apply to a
    program written as Python (AIL_SURFACE=python). The AIL spelling keeps its own convention (a
    comparison in an `-> int` function is the 0/1 it always was)."""
    return os.environ.get('AIL_SURFACE') == 'python'


def _mark(name):
    return '{}' + name


def _real(names):
    """The identifiers of a `lists` set (without the dict markers), sorted."""
    return sorted(n for n in names if not n.startswith('{'))


class _Env:
    """What a bool expression is judged by before typing (see the module note)."""

    def __init__(self, info, classes, methods, functions, class_fields):
        self.classes = classes
        self.functions = {f.name for f in functions}
        self.top_fns = {name for name in self.functions if name in info.fns}
        self.top_list_fns = {name for name in self.functions if name in info.list_fns}
        self.top_dict_fns = {name for name in self.functions if name in info.dict_fns}
        field_kinds, method_kinds, list_method_kinds, dict_method_kinds = {}, {}, {}, {}
        for cname in classes:
            for field in class_fields.get(cname, ()):
                kind = ('bool' if (cname, field) in info.fields
                        else 'dict' if (cname, field) in info.dict_fields
                        else 'list' if (cname, field) in info.list_fields else 'other')
                field_kinds.setdefault(field, set()).add(kind)
            for mname in methods[cname]:
                if mname != '__init__':
                    compiled = '%s__%s' % (cname, mname)
                    method_kinds.setdefault(mname, set()).add(compiled in info.fns)
                    list_method_kinds.setdefault(mname, set()).add(compiled in info.list_fns)
                    dict_method_kinds.setdefault(mname, set()).add(compiled in info.dict_fns)
        self.bool_fields = {f for f, kinds in field_kinds.items() if kinds == {'bool'}}
        self.list_fields = {f for f, kinds in field_kinds.items() if kinds == {'list'} or kinds == {'dict'}}
        self.dict_fields = {f for f, kinds in field_kinds.items() if kinds == {'dict'}}
        self.bool_methods = {m for m, kinds in method_kinds.items() if kinds == {True}}
        self.list_methods = {m for m, kinds in list_method_kinds.items() if kinds == {True}}
        self.dict_methods = {m for m, kinds in dict_method_kinds.items() if kinds == {True}}
        self.user_methods = set(method_kinds)

    # The questions `boolish` asks of its environment; the compiler's typed environment answers
    # them from real types (pyfunc._TypedBoolEnv).
    def attr_bool(self, node):
        return node.attr in self.bool_fields

    def attr_list(self, node):
        return node.attr in self.list_fields

    def attr_dict(self, node):
        return node.attr in self.dict_fields

    def call_info(self, node):
        """(bool, list, dict) for a call of a function, class or method of the program, else None."""
        f = node.func
        if isinstance(f, ast.Name):
            if f.id in self.functions:
                return (f.id in self.top_fns, f.id in self.top_list_fns, f.id in self.top_dict_fns)
            if f.id in self.classes:
                return (False, False, False)
        elif isinstance(f, ast.Attribute) and f.attr in self.user_methods:
            return (f.attr in self.bool_methods, f.attr in self.list_methods, f.attr in self.dict_methods)
        return None

    def predicate_call(self, node):
        f = node.func
        return isinstance(f, ast.Attribute) and (f.attr in STR_PREDICATES or f.attr in SET_PREDICATES)


def _vacuous(node):
    """An empty list or dict: it holds no element that could be a bool or a number."""
    if isinstance(node, ast.List):
        return not node.elts
    if isinstance(node, ast.Dict):
        return not node.keys
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ('list', 'dict') and not node.args and not node.keywords)


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
        return env.attr_bool(node)
    if isinstance(node, ast.Subscript):
        return not isinstance(node.slice, ast.Slice) and bool_list_value(node.value, env, names, lists)
    if isinstance(node, ast.BinOp):
        return (isinstance(node.op, (ast.BitAnd, ast.BitOr, ast.BitXor))
                and boolish(node.left, env, names, lists) and boolish(node.right, env, names, lists))
    if isinstance(node, ast.Call):
        info = env.call_info(node)
        if info is not None:
            return info[0]
        f = node.func
        if isinstance(f, ast.Name):
            if f.id in ('max', 'min') and not node.keywords and node.args:
                if len(node.args) == 1:
                    return bool_seq_value(node.args[0], env, names, lists)
                return all(boolish(a, env, names, lists) for a in node.args)
            return f.id in BOOL_BUILTINS
        if isinstance(f, ast.Attribute):
            if f.attr == 'pop' and bool_list_value(f.value, env, names, lists):
                return len(node.args) <= 1 or (len(node.args) == 2 and is_dict_value(f.value, env, lists)
                                               and boolish(node.args[1], env, names, lists))
            if (f.attr == 'get' and len(node.args) == 2 and is_dict_value(f.value, env, lists)
                    and bool_list_value(f.value, env, names, lists)):
                return boolish(node.args[1], env, names, lists)
            return env.predicate_call(node)
    return False


def is_dict_value(node, env, lists):
    """True when `node` is a dict (what iterating it yields are keys, not values)."""
    if isinstance(node, (ast.Dict, ast.DictComp)):
        return True
    if isinstance(node, ast.Name):
        return _mark(node.id) in lists
    if isinstance(node, ast.Attribute):
        return env.attr_dict(node)
    if isinstance(node, ast.IfExp):
        return is_dict_value(node.body, env, lists) and is_dict_value(node.orelse, env, lists)
    if isinstance(node, ast.Call):
        info = env.call_info(node)
        if info is not None:
            return info[2]
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == 'copy' and not node.args:
            return is_dict_value(f.value, env, lists)
        if isinstance(f, ast.Name) and f.id == 'dict':
            return True
    return False


def bool_seq_value(node, env, names, lists):
    """A list (or `d.values()`) whose every element is a bool; iterating it yields those elements."""
    return bool_list_value(node, env, names, lists) and not is_dict_value(node, env, lists)


def bool_list_value(node, env, names, lists):
    """True when `node` is a list or dict whose every element (value) is a bool."""
    if isinstance(node, ast.List):
        return bool(node.elts) and all(boolish(e, env, names, lists) for e in node.elts)
    if isinstance(node, ast.ListComp):
        return boolish(node.elt, env, names, lists)
    if isinstance(node, ast.Dict):
        return (bool(node.values) and all(k is not None for k in node.keys)
                and all(boolish(v, env, names, lists) for v in node.values))
    if isinstance(node, ast.DictComp):
        return boolish(node.value, env, names, lists)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return (bool_seq_value(node.left, env, names, lists)
                or bool_seq_value(node.right, env, names, lists))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return (bool_seq_value(node.left, env, names, lists)
                and bool_seq_value(node.right, env, names, lists))
    if isinstance(node, ast.Name):
        return node.id in lists
    if isinstance(node, ast.Attribute):
        return env.attr_list(node)
    if isinstance(node, ast.IfExp):
        return (bool_list_value(node.body, env, names, lists)
                and bool_list_value(node.orelse, env, names, lists))
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        return bool_seq_value(node.value, env, names, lists)
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == 'copy' and not node.args:
            return bool_list_value(f.value, env, names, lists)
        if (isinstance(f, ast.Attribute) and f.attr == 'values' and not node.args
                and is_dict_value(f.value, env, lists)):
            return bool_list_value(f.value, env, names, lists)
        if isinstance(f, ast.Name) and f.id in ('sorted', 'list', 'reversed') and len(node.args) == 1:
            return bool_seq_value(node.args[0], env, names, lists)
        info = env.call_info(node)
        if info is not None:
            return info[1]
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


def _call_of(node, method, *, args=()):
    return ast.Call(func=ast.Attribute(value=node, attr=method, ctx=ast.Load()), args=list(args), keywords=[])


def _tuple_loop(target, it):
    """For `for k, v in d.items()`, `for i, x in enumerate(xs)` and `for a, b in zip(xs, ys)`: the
    iterable each target name draws its values from ({name: iterable}), else None."""
    if not (isinstance(target, ast.Tuple) and all(isinstance(e, ast.Name) for e in target.elts)
            and isinstance(it, ast.Call) and not it.keywords):
        return None
    f = it.func
    if (isinstance(f, ast.Attribute) and f.attr == 'items' and not it.args and len(target.elts) == 2):
        return {target.elts[1].id: _call_of(f.value, 'values')}
    if isinstance(f, ast.Name) and f.id == 'enumerate' and len(it.args) in (1, 2) and len(target.elts) == 2:
        return {target.elts[1].id: it.args[0]}
    if isinstance(f, ast.Name) and f.id == 'zip' and len(it.args) == len(target.elts):
        return {e.id: a for e, a in zip(target.elts, it.args)}
    return None


def _bit_augassign(node):
    return (isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name)
            and isinstance(node.op, (ast.BitAnd, ast.BitOr, ast.BitXor)))


def _facts(f):
    """What a function assigns: values by name, `for` iterables, names a number can reach
    (`poisoned`), container stores (`breaks`), and where each poisoning happens."""
    values, loops, poisoned, breaks = {}, {}, set(), {}
    poison_at = {}
    for node in _own_nodes(f):
        if _bit_augassign(node):
            continue
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
        elif _bit_augassign(node):
            # `ok &= cond` is `ok = ok & cond`: a bool when both are
            values.setdefault(node.target.id, []).append(ast.copy_location(ast.BinOp(
                left=ast.Name(id=node.target.id, ctx=ast.Load()), op=node.op, right=node.value), node))
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
                mapped = _tuple_loop(node.target, node.iter)
                if mapped is None:
                    poisoned |= _bound_names(node.target)
                else:
                    for name in _bound_names(node.target):
                        if name in mapped:
                            loops.setdefault(name, []).append(mapped[name])
                        else:
                            poisoned.add(name)
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
            name = node.func.value.id
            if node.func.attr in ('append', 'insert') and node.args:
                breaks.setdefault(name, []).append(node.args[-1])
            elif node.func.attr in ('extend', 'update'):
                breaks.setdefault(name, []).append(
                    ('list', node.args[0] if node.args else None))
            elif node.func.attr == 'setdefault' and len(node.args) == 2:
                breaks.setdefault(name, []).append(node.args[1])
            elif node.func.attr == 'setdefault':
                breaks.setdefault(name, []).append(None)
    return values, loops, poisoned, breaks, poison_at


def _container_ok(n, env, names, lists, values, breaks):
    """Whether the candidate bool container `n` still holds only bools."""
    if n in names:
        return False
    for v in values.get(n, ()):
        if not (_vacuous(v) or bool_list_value(v, env, names, lists)):
            return False
    for brk in breaks.get(n, ()):
        if brk is None:
            return False
        if isinstance(brk, tuple):
            if brk[1] is None or not (_vacuous(brk[1]) or bool_list_value(brk[1], env, names, lists)):
                return False
        elif not boolish(brk, env, names, lists):
            return False
    return True


def _has_evidence(n, env, names, lists, values, breaks, fed=()):
    """Whether something shows that the container `n` holds a bool: a non-empty bool literal or
    comprehension assigned to it, a bool stored or appended into it, or a call that hands it to a
    parameter that does. An empty list that nothing fills is not a bool list; a program without bools
    must come out of the compiler as it always did."""
    if n in fed:
        return True
    if any(not _vacuous(v) for v in values.get(n, ())):
        return True
    for brk in breaks.get(n, ()):
        if isinstance(brk, tuple):
            if brk[1] is not None and not _vacuous(brk[1]):
                return True
        elif brk is not None and boolish(brk, env, names, lists):
            return True
    return False


def _solve(env, names, lists, fixed_names, fixed_lists, values, loops, breaks, fed=()):
    """Shrink the candidate bool names and containers to a fixed point (in place)."""
    changed = True
    while changed:
        changed = False
        for n in _real(lists):
            if _mark(n) not in lists and any(is_dict_value(v, env, lists) for v in values.get(n, ())):
                lists.add(_mark(n))
                changed = True
        for n in sorted(names - fixed_names):
            if not (all(boolish(v, env, names, lists) for v in values.get(n, ()))
                    and all(bool_seq_value(it, env, names, lists) for it in loops.get(n, ()))):
                names.discard(n)
                changed = True
        for n in _real(lists - fixed_lists):
            if not (_container_ok(n, env, names, lists, values, breaks)
                    and _has_evidence(n, env, names, lists, values, breaks, fed)):
                lists.discard(n)
                lists.discard(_mark(n))
                changed = True


def _scope(env, f, entry, extra_names, extra_lists, module_bools, facts, fed=()):
    """(names, lists) of one function: the bool locals and the bool containers."""
    fixed_names, fixed_lists, _annotated = entry
    params = {a.arg for a in (*f.args.posonlyargs, *f.args.args, *f.args.kwonlyargs)}
    fixed_names = set(fixed_names) | set(extra_names) | (set(module_bools) - params)
    fixed_lists = set(fixed_lists) | set(extra_lists)
    values, loops, poisoned, breaks, _at = facts
    free = (set(values) | set(loops)) - params - poisoned
    names = fixed_names | (free - fixed_lists)
    lists = fixed_lists | ((set(values) - params - poisoned) - fixed_names)
    _solve(env, names, lists, fixed_names, fixed_lists, values, loops, breaks, fed)
    return names, lists


def _is_self(node):
    return isinstance(node, ast.Name) and node.id == 'self'


def _field_events(nodes):
    """Stores to attributes in `nodes`: (attr, kind, value, receiver). kind is 'set' (`x.f = v`),
    'elem' (`x.f[i] = v`, `x.f.append(v)`), 'ext' (`x.f.extend(v)`, `x.f.update(v)`) or 'bad' (a store
    that keeps no kind: `x.f += 1`, a loop target); receiver is the expression the attribute is read from."""
    for node in nodes:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                if isinstance(t, ast.Attribute):
                    yield t.attr, 'set', node.value, t.value
                elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute):
                    yield t.value.attr, 'elem', node.value, t.value.value
                elif isinstance(t, (ast.Tuple, ast.List)):
                    pairs = (list(zip(t.elts, node.value.elts))
                             if isinstance(node.value, (ast.Tuple, ast.List))
                             and len(node.value.elts) == len(t.elts) else None)
                    for i, sub in enumerate(t.elts):
                        if isinstance(sub, ast.Attribute):
                            if pairs is not None and not isinstance(pairs[i][0], ast.Starred):
                                yield sub.attr, 'set', pairs[i][1], sub.value
                            else:
                                yield sub.attr, 'bad', None, sub.value
        elif isinstance(node, ast.AugAssign):
            target = node.target.value if isinstance(node.target, ast.Subscript) else node.target
            if isinstance(target, ast.Attribute):
                yield target.attr, 'bad', None, target.value
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            for sub in ast.walk(node.target):
                if isinstance(sub, ast.Attribute):
                    yield sub.attr, 'bad', None, sub.value
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Attribute):
            attr, method = node.func.value.attr, node.func.attr
            on_self = node.func.value.value
            if method in ('append', 'insert') and node.args:
                yield attr, 'elem', node.args[-1], on_self
            elif method in ('extend', 'update'):
                yield attr, 'ext', node.args[0] if node.args else None, on_self
            elif method == 'setdefault':
                yield attr, 'elem', node.args[1] if len(node.args) == 2 else None, on_self


def _class_fields(classes, methods):
    """{class: names of its fields}: `self.f` stores in its methods and the `__init__` parameters
    (a parameter declared bool is a field of that name)."""
    out = {}
    for cname in classes:
        names = set()
        for mname, m in methods[cname].items():
            if mname == '__init__':
                names.update(a.arg for a in m.args.args[1:])
            for attr, _kind, _value, _recv in _field_events(_own_nodes(m)):
                names.add(attr)
        out[cname] = names
    return out


def _container_use(f, p):
    """Whether `f` uses its parameter `p` as a list or dict (indexes it, iterates it, calls a method)."""
    for n in ast.walk(f):
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == p:
            return True
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name) and n.func.value.id == p):
            return True
        if isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)) and isinstance(n.iter, ast.Name) \
                and n.iter.id == p:
            return True
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'len'
                and len(n.args) == 1 and isinstance(n.args[0], ast.Name) and n.args[0].id == p):
            return True
    return False


def _simple(f):
    a = f.args
    return not (a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs or f.decorator_list)


def _infer(info, tree, units, classes, methods, functions, declared, slots, class_fields,
           facts, module_bools):
    """Unannotated parameters, results and fields that hold bools (or bool lists / dicts). A parameter
    is a bool when every call passes a bool for it (a comparison, `not`, True / False, a bool name or
    call) and the function only stores bools into it; a result when every `return` is one; a field
    when every store to its name is one. Found by shrinking from "all of them" to a fixed point, since
    a bool parameter makes more returns bools. A parameter that some calls pass a bool and others a
    number cannot be told apart by kind and is refused by name (Python keeps each value's own type;
    an int64 cannot); so is a field, a result or a container that mixes them."""
    top = {f.name: f for f in functions}
    unit_of = {key: (f, owner) for key, f, owner in units}

    def resolve(cname, mname):
        seen = set()
        while cname in classes and cname not in seen:
            seen.add(cname)
            if mname in methods[cname]:
                return cname
            bases = classes[cname].bases
            cname = bases[0].id if len(bases) == 1 and isinstance(bases[0], ast.Name) else None
        return None

    def key_of(cname, mname):
        owner = resolve(cname, mname)
        if owner is None:
            return None
        return owner + '.__init__' if mname == '__init__' else '%s__%s' % (owner, mname)

    callees = {}                  # key -> (def, index of the first parameter a call fills)
    method_keys = {}              # method name -> [keys]
    for name, f in top.items():
        callees[name] = (f, 0)
    for cname in classes:
        for mname, m in methods[cname].items():
            if mname == '__init__':
                callees[cname + '.__init__'] = (m, 1)
            else:
                callees['%s__%s' % (cname, mname)] = (m, 1)
                method_keys.setdefault(mname, []).append('%s__%s' % (cname, mname))
    sites = {key: [] for key in callees}
    as_value = set()
    keyed = list(units) + [(None, node, None) for node in tree.body
                           if not isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    for ckey, f, owner in keyed:
        walk = list(ast.walk(f))
        func_ids = {id(n.func) for n in walk if isinstance(n, ast.Call)}
        for n in walk:
            if isinstance(n, ast.Call):
                fn = n.func
                if isinstance(fn, ast.Name):
                    if fn.id in top:
                        sites[fn.id].append((ckey, n, 0))
                    elif fn.id in classes:
                        k = key_of(fn.id, '__init__')
                        if k in callees:
                            sites[k].append((ckey, n, 0))
                elif isinstance(fn, ast.Attribute):
                    v = fn.value
                    if isinstance(v, ast.Name) and v.id in classes:
                        k = key_of(v.id, fn.attr)
                        if k in callees:
                            sites[k].append((ckey, n, 1))
                    elif (isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == 'super'):
                        bases = classes[owner].bases if owner in classes else ()
                        k = (key_of(bases[0].id, fn.attr)
                             if len(bases) == 1 and isinstance(bases[0], ast.Name) else None)
                        if k in callees:
                            sites[k].append((ckey, n, 0))
                    else:
                        for k in method_keys.get(fn.attr, ()):
                            sites[k].append((ckey, n, 0))
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in func_ids:
                if n.id in top:
                    as_value.add(n.id)
                elif n.id in classes:
                    as_value.add(key_of(n.id, '__init__'))
            elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and id(n) not in func_ids:
                for k in method_keys.get(n.attr, ()):
                    as_value.add(k)

    base_fns, base_lfns, base_dfns = set(info.fns), set(info.list_fns), set(info.dict_fns)
    base_fields, base_lfields, base_dfields = set(info.fields), set(info.list_fields), set(info.dict_fields)

    # candidate parameters: (callee, name) -> kinds still possible: 'b' bool, 'l' list, 'd' dict
    cand_p = {}
    for key, (f, off) in callees.items():
        if not (_simple(f) and key not in as_value and sites[key]) or any(
                isinstance(n, (ast.Yield, ast.YieldFrom)) for n in _own_nodes(f)):
            continue
        for p in f.args.args[off:]:
            if p.annotation is None:
                cand_p[(key, p.arg)] = {'l', 'd'} if _container_use(f, p.arg) else {'b', 'l', 'd'}
    # candidate results
    cand_r = {}
    for key, (f, off) in callees.items():
        if key.endswith('.__init__') or f.returns is not None or key in base_fns | base_lfns:
            continue
        returns = [n for n in _own_nodes(f) if isinstance(n, ast.Return)]
        if (returns and all(r.value is not None for r in returns)
                and isinstance(f.body[-1], (ast.Return, ast.Raise))
                and not any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in _own_nodes(f))):
            cand_r[key] = {'b', 'l', 'd'}
    # candidate fields, keyed by (class, name), with every store that can reach them: a store through
    # `self` reaches the class and the bases that define the name, any other receiver (its class is
    # not known before typing) every class that has the name; the element stores of a list or dict
    # reach only classes whose field is one (a scalar field has no elements)
    field_names = set().union(*class_fields.values()) if class_fields else set()
    chain = {}
    for cname in classes:
        order, seen, c = [], set(), cname
        while c in classes and c not in seen:
            seen.add(c)
            order.append(c)
            bases = classes[c].bases
            c = bases[0].id if len(bases) == 1 and isinstance(bases[0], ast.Name) else None
        chain[cname] = order
    declared_other = set()             # (class, field) annotated with something other than a bool kind
    for cname in classes:
        for m in methods[cname].values():
            for node in ast.walk(m):
                if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Attribute)
                        and _is_self(node.target.value)
                        and (cname, node.target.attr) not in base_fields | base_lfields):
                    declared_other.add((cname, node.target.attr))
    def receiver_classes(key, f, owner):
        """{name: class} for the locals and parameters of one function whose class is plain to see:
        a parameter annotated with a class, a name only ever assigned `Cls(...)`."""
        out = {}
        for a in (*f.args.posonlyargs, *f.args.args, *f.args.kwonlyargs):
            if isinstance(a.annotation, ast.Name) and a.annotation.id in classes:
                out[a.arg] = a.annotation.id
        values = facts[key][0]
        for name, vs in values.items():
            made = {v.func.id if isinstance(v, ast.Call) and isinstance(v.func, ast.Name)
                    and v.func.id in classes else None for v in vs}
            if len(made) == 1 and None not in made and name not in out:
                out[name] = made.pop()
        for name in facts[key][2]:
            out.pop(name, None)
        return out

    owned = set()
    raw = []                           # (unit key, class of the receiver or None, attr, kind, value, on_self)
    for key, f, owner in units:
        nodes = list(_own_nodes(f))
        owned.update(id(n) for n in nodes)
        known = receiver_classes(key, f, owner)
        for a, k, v, recv in _field_events(nodes):
            if a not in field_names:
                continue
            if _is_self(recv) and owner in classes:
                raw.append((key, owner, a, k, v, True))
            elif isinstance(recv, ast.Name) and recv.id in known:
                raw.append((key, known[recv.id], a, k, v, True))
            else:
                raw.append((key, None, a, k, v, False))
    raw += [(None, None, a, k, v, False)
            for a, k, v, recv in _field_events(n for n in ast.walk(tree) if id(n) not in owned)
            if a in field_names]

    def reach(owner, attr, on_self):
        if on_self and owner in classes:
            return [c for c in chain[owner] if attr in class_fields[c]]
        return [c for c in classes if attr in class_fields[c]]

    def containerish(v):
        return not (isinstance(v, (ast.Constant, ast.Compare, ast.BoolOp, ast.IfExp))
                    or (isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.Not)))
    by_key = {}
    for key, owner, attr, kind, value, on_self in raw:
        if kind in ('set', 'bad'):
            for c in reach(owner, attr, on_self):
                by_key.setdefault((c, attr), []).append((key, kind, value, on_self))
    container_class = {ck for ck, evs in by_key.items()
                       if any(kind == 'set' and containerish(v) for _k, kind, v, _o in evs)}
    for key, owner, attr, kind, value, on_self in raw:
        if kind in ('elem', 'ext'):
            for c in reach(owner, attr, on_self):
                if on_self or (c, attr) in container_class:
                    by_key.setdefault((c, attr), []).append((key, kind, value, on_self))
    cand_f = {}
    for ck, evs in by_key.items():
        if ck not in declared_other and any(kind == 'set' for _k, kind, _v, _o in evs):
            cand_f[ck] = {'b', 'l', 'd'}

    names_of, lists_of = {}, {}

    def build():
        info.fns = base_fns | {k for k, kinds in cand_r.items() if 'b' in kinds}
        info.list_fns = base_lfns | {k for k, kinds in cand_r.items() if kinds & {'l', 'd'}}
        info.dict_fns = base_dfns | {k for k, kinds in cand_r.items() if kinds == {'d'}}
        info.fields = set(base_fields)
        info.list_fields = set(base_lfields)
        info.dict_fields = set(base_dfields)
        for cname in classes:
            for attr in class_fields[cname]:
                kinds = cand_f.get((cname, attr))
                if not kinds:
                    continue
                if 'b' in kinds:
                    info.fields.add((cname, attr))
                elif kinds == {'d'}:
                    info.list_fields.add((cname, attr))
                    info.dict_fields.add((cname, attr))
                elif kinds & {'l', 'd'}:
                    info.list_fields.add((cname, attr))
        return _Env(info, classes, methods, functions, class_fields)

    def param_sets(key):
        extra_n, extra_l = set(), set()
        for (k, p), kinds in cand_p.items():
            if k != key:
                continue
            if 'b' in kinds:
                extra_n.add(p)
            elif kinds & {'l', 'd'}:
                extra_l.add(p)
                if kinds == {'d'}:
                    extra_l.add(_mark(p))
        return extra_n, extra_l

    def site_arg(call, skip, f, off, p):
        pi = next(i for i, a in enumerate(f.args.args) if a.arg == p)
        if any(isinstance(x, ast.Starred) for x in call.args) or any(k.arg is None for k in call.keywords):
            return None
        ai = pi - off + skip
        if ai < len(call.args):
            return call.args[ai]
        kw = next((k.value for k in call.keywords if k.arg == p), None)
        if kw is not None:
            return kw
        ndef = len(f.args.defaults)
        if pi >= len(f.args.args) - ndef:
            return f.args.defaults[pi - (len(f.args.args) - ndef)]
        return None

    mixed = {}
    env = None
    for _round in range(400):
        env = build()
        names_of, lists_of = {}, {}
        for key, f, owner in units:
            extra_n, extra_l = param_sets(key)
            names_of[key], lists_of[key] = _scope(env, f, declared[key], extra_n, extra_l,
                                                  module_bools, facts[key])
        changed = False
        # results
        for key, kinds in cand_r.items():
            f = unit_of[key][0]
            rets = [r.value for r in _own_nodes(f) if isinstance(r, ast.Return)]
            names, lists = names_of[key], lists_of[key]
            new = set()
            if 'b' in kinds and all(boolish(v, env, names, lists) for v in rets):
                new.add('b')
            if kinds & {'l', 'd'} and any(not _vacuous(v) for v in rets) and all(
                    _vacuous(v) or bool_list_value(v, env, names, lists) for v in rets):
                if all(is_dict_value(v, env, lists) for v in rets):
                    new |= kinds & {'d'}
                elif not any(is_dict_value(v, env, lists) for v in rets):
                    new |= kinds & {'l'}
            if new != kinds:
                cand_r[key] = new
                changed = True
        # parameters
        for (key, p), kinds in list(cand_p.items()):
            f, off = callees[key]
            ukey = key
            facts_f = facts[ukey]
            values, loops, poisoned, breaks, _at = facts_f
            new = set()
            verdict = {k: [] for k in kinds}
            nonvac = {k: False for k in kinds}
            for caller, call, skip in sites[key]:
                arg = site_arg(call, skip, f, off, p)
                names_c = names_of.get(caller, set())
                lists_c = lists_of.get(caller, set())
                for k in kinds:
                    if arg is None:
                        verdict[k].append(None)
                    elif k == 'b':
                        verdict[k].append(boolish(arg, env, names_c, lists_c))
                    elif k == 'l':
                        ok = bool_seq_value(arg, env, names_c, lists_c)
                        verdict[k].append(ok or (_vacuous(arg) and not isinstance(arg, ast.Dict)))
                        nonvac[k] = nonvac[k] or ok
                    else:
                        ok = is_dict_value(arg, env, lists_c) and bool_list_value(arg, env, names_c, lists_c)
                        verdict[k].append(ok or (isinstance(arg, ast.Dict) and _vacuous(arg)))
                        nonvac[k] = nonvac[k] or ok
            for k in kinds:
                vs = verdict[k]
                if not vs or not all(v is True for v in vs):
                    continue
                names, lists = names_of[ukey], lists_of[ukey]
                if k == 'b':
                    if p not in poisoned and all(boolish(v, env, names, lists) for v in values.get(p, ())):
                        new.add('b')
                elif _container_ok(p, env, names - {p}, lists, values, breaks) and (
                        nonvac[k] or _has_evidence(p, env, names, lists, {}, breaks)):
                    new.add(k)
            if len(new) > 1:
                new = set()
            if new != kinds:
                cand_p[(key, p)] = new
                changed = True
        # fields
        for ck, kinds in list(cand_f.items()):
            attr = ck
            new = set()
            evs = by_key[ck]
            sets = [(k, v) for k, kind, v, _o in evs if kind == 'set']
            elems = [(k, v) for k, kind, v, _o in evs if kind == 'elem']
            exts = [(k, v) for k, kind, v, _o in evs if kind == 'ext']
            bad = any(kind == 'bad' for _k, kind, _v, _o in evs)
            if bad:
                cand_f[ck] = set()
                changed = changed or bool(kinds)
                continue

            def scope(k):
                return (names_of.get(k, set()), lists_of.get(k, set()))
            if 'b' in kinds and not elems and not exts and all(
                    boolish(v, env, *scope(k)) for k, v in sets):
                new.add('b')
            if kinds & {'l', 'd'} and (elems or exts or any(not _vacuous(v) for _k, v in sets)) and all(
                    v is not None for _k, v in elems) and all(
                    boolish(v, env, *scope(k)) for k, v in elems) and all(
                    v is not None and (_vacuous(v) or bool_list_value(v, env, *scope(k)))
                    for k, v in exts) and all(
                    _vacuous(v) or bool_list_value(v, env, *scope(k)) for k, v in sets):
                shapes = {is_dict_value(v, env, scope(k)[1]) for k, v in sets}
                if shapes == {True}:
                    new |= kinds & {'d'}
                elif shapes == {False}:
                    new |= kinds & {'l'}
            if len(new) > 1:
                new = set()
            if new != kinds:
                cand_f[ck] = new
                changed = True
        if not changed:
            break
    else:
        # no fixed point (cannot happen with shrinking sets, but never guess): nothing inferred
        for d in (cand_r, cand_p, cand_f):
            for key in d:
                d[key] = set()
        env = build()
        for key, f, owner in units:
            names_of[key], lists_of[key] = _scope(env, f, declared[key], set(), set(),
                                                  module_bools, facts[key])

    # what was decided
    for (key, p), kinds in cand_p.items():
        f, off = callees[key]
        if not kinds:
            continue
        pi = next(i for i, a in enumerate(f.args.args) if a.arg == p)
        if 'b' in kinds:
            declared[key][0].add(p)
        else:
            declared[key][1].add(p)
            if kinds == {'d'}:
                declared[key][1].add(_mark(p))
        slots[key].append((pi - off, p, 'b' not in kinds))

    # mixed: some stores / calls / returns are bools and others are not
    for (key, p), kinds in cand_p.items():
        if kinds:
            continue
        f, off = callees[key]
        values, loops, poisoned, breaks, _at = facts[key]
        names, lists = names_of.get(key, set()), lists_of.get(key, set())
        flags_b, flags_l = [], []
        for caller, call, skip in sites[key]:
            arg = site_arg(call, skip, f, off, p)
            if arg is None:
                continue
            nc, lc = names_of.get(caller, set()), lists_of.get(caller, set())
            flags_b.append(boolish(arg, env, nc, lc))
            flags_l.append(bool_list_value(arg, env, nc, lc) and not _vacuous(arg))
        elem_bools = any(b is not None and not isinstance(b, tuple) and boolish(b, env, names, lists)
                         for b in breaks.get(p, ()))
        at = next(a for a in f.args.args if a.arg == p)
        label = ('parameter `%s` of %s()' % (p, key.replace('.__init__', '').replace('__', '.')))
        if any(flags_b) and not all(flags_b) and (key in top or _python_surface()):
            _fail(info.error, '%s gets a bool from some calls and a number from others; '
                  'Python keeps each value\'s own type and a number would print as 1 / 0.\n'
                  '  write instead: pass the same kind everywhere (`int(flag)` or a comparison)'
                  % label, at)
        if _python_surface() and ((any(flags_l) and not all(flags_l))
                                  or (elem_bools and not all(flags_l) and flags_l)):
            _fail(info.error, '%s gets a list of bools from some calls and a list of numbers from '
                  'others; Python keeps each element\'s own type.\n'
                  '  write instead: pass the same kind everywhere' % label, at)

    for key, kinds in cand_r.items():
        f = unit_of[key][0]
        if kinds or not _python_surface():
            continue
        rets = [r.value for r in _own_nodes(f) if isinstance(r, ast.Return)]
        names, lists = names_of[key], lists_of[key]
        flags = [boolish(v, env, names, lists) for v in rets]
        if any(flags) and not all(flags):
            at = next(v for v, fl in zip(rets, flags) if not fl)
            _fail(info.error, '%s() returns a bool on some paths and a number on others; '
                  'Python keeps each value\'s own type (True / 1).\n'
                  '  write instead: return the same kind on every path (`int(flag)`, or a comparison)'
                  % f.name, at)
        lflags = [bool_list_value(v, env, names, lists) and not _vacuous(v) for v in rets]
        if any(lflags) and not all(_vacuous(v) or fl for v, fl in zip(rets, lflags)):
            at = next(v for v, fl in zip(rets, lflags) if not fl and not _vacuous(v))
            _fail(info.error, '%s() returns a list of bools on some paths and another list on others'
                  % f.name, at)

    for ck, kinds in cand_f.items():
        if kinds or not _python_surface():
            continue
        attr = ck[1]
        evs = by_key[ck]
        sets = [(k, v) for k, kind, v, _o in evs if kind == 'set']
        elems = [(k, v) for k, kind, v, _o in evs if kind == 'elem' and v is not None]

        def scope(k):
            return (names_of.get(k, set()), lists_of.get(k, set()))
        flags = [boolish(v, env, *scope(k)) for k, v in sets]
        lflags = [bool_list_value(v, env, *scope(k)) and not _vacuous(v) for k, v in sets]
        eflags = [boolish(v, env, *scope(k)) for k, v in elems]
        if any(flags) and not all(flags):
            at = next(v for (k, v), fl in zip(sets, flags) if not fl)
            _fail(info.error, 'field `%s` is assigned a bool in some places and a number in others; '
                  'Python keeps each value\'s own type (True / 1).\n'
                  '  write instead: store the same kind everywhere (`int(flag)`, or a comparison)'
                  % attr, at)
        if any(lflags) and not all(_vacuous(v) or fl for (k, v), fl in zip(sets, lflags)):
            at = next(v for (k, v), fl in zip(sets, lflags) if not fl and not _vacuous(v))
            _fail(info.error, 'field `%s` holds a list of bools in some places and another list in others' % attr, at)
        if any(eflags) and (not all(eflags) or (sets and not any(lflags))):
            at = next((v for (k, v), fl in zip(elems, eflags) if not fl),
                      elems[0][1])
            _fail(info.error, 'field `%s` is a list or dict that gets bools and numbers (Python keeps each '
                  'element\'s own type)' % attr, at)
    return env


def _mixed_literals(units, tree, env, names_of, lists_of, error):
    """A list or dict literal, a conditional or a `max` / `min` whose operands are bools in part:
    Python keeps each one's own type, a slot of one kind cannot."""
    if not _python_surface():
        return
    for key, f, owner in units:
        names, lists = names_of[key], lists_of[key]
        for node in _own_nodes(f):
            operands = None
            if isinstance(node, ast.List):
                operands = node.elts
            elif isinstance(node, ast.Dict):
                operands = node.values
            elif isinstance(node, ast.IfExp):
                operands = [node.body, node.orelse]
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id in ('max', 'min') and len(node.args) >= 2 and not node.keywords):
                operands = node.args
            if not operands or len(operands) < 2:
                continue
            flags = [boolish(e, env, names, lists) for e in operands]
            if any(flags) and not all(flags):
                # a conditional between a bool and the number it was made from reads as a number
                _fail(error, '`%s` mixes bools and numbers; Python keeps each value\'s own type and a '
                      'number would print as 1 / 0.\n'
                      '  write instead: make every operand a bool (or `int(...)` every operand)'
                      % _show(node), node)


def _observed_names(f):
    """Names that appear in the argument of a text call (print, str, repr, format) or an f-string."""
    out = set()
    for node in _own_nodes(f):
        if isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Name) and node.func.id in TEXT_CALLS)
                or (isinstance(node.func, ast.Attribute) and node.func.attr == 'format')):
            for arg in [*node.args, *(k.value for k in node.keywords)]:
                out |= {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)}
        elif isinstance(node, ast.FormattedValue):
            out |= {n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)}
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            out |= {n.id for n in ast.walk(node.right) if isinstance(n, ast.Name)}
    return out


def scan(tree, error, module_bools=frozenset()):
    """Record and rewrite every bool annotation in `tree`; return a BoolInfo (see module note).
    `module_bools` are the module variables that start as True / False and that functions rebind
    with `global`: each is a bool in every function that does not take a parameter of that name,
    and every store into one must be a bool."""
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    if 'bool' in classes:
        return EMPTY
    info = BoolInfo()
    info.error = error
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
            elif kind in ('list', 'dict'):
                info.list_fields.add((cname, arg.arg))
                if kind == 'dict':
                    info.dict_fields.add((cname, arg.arg))
        if init is not None:
            units.append((cname + '.__init__', init, cname))
        for m in methods[cname].values():                     # `self.done: bool = True`
            for node in ast.walk(m):
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Attribute):
                    kind, node.annotation = _rewrite(node.annotation)
                    if kind and isinstance(node.target.value, ast.Name) and node.target.value.id == 'self':
                        attr = node.target.attr
                        (info.fields if kind == 'bool' else info.list_fields).add((cname, attr))
                        if kind == 'dict':
                            info.dict_fields.add((cname, attr))
    slots = {}                     # compiled name -> [(position, name, is_list)]
    declared = {}                  # compiled name -> (bool names, bool lists, annotated locals)
    int_slots = {}                 # compiled name -> parameters / locals the program declares int
    for key, f, owner in units:
        names, lists, annotated = set(), set(), set()
        slots[key] = []
        int_slots[key] = {'params': set(), 'ret': False, 'locals': set()}
        if key.endswith('.__init__'):
            for arg in f.args.args[1:]:
                if (owner, arg.arg) in info.fields:
                    names.add(arg.arg)
                elif (owner, arg.arg) in info.list_fields:
                    lists.add(arg.arg)
                    if (owner, arg.arg) in info.dict_fields:
                        lists.add(_mark(arg.arg))
                elif isinstance(arg.annotation, ast.Name) and arg.annotation.id in INT_NAMES:
                    int_slots[key]['params'].add(arg.arg)
            declared[key] = (names, lists, annotated)
            continue
        positional = f.args.args[1:] if owner else [*f.args.posonlyargs, *f.args.args]
        for index, arg in enumerate([*positional, *f.args.kwonlyargs]):
            kind, arg.annotation = _rewrite(arg.annotation)
            if kind:
                (names if kind == 'bool' else lists).add(arg.arg)
                if kind == 'dict':
                    lists.add(_mark(arg.arg))
                slots[key].append((index if index < len(positional) else None, arg.arg, kind != 'bool'))
            elif isinstance(arg.annotation, ast.Name) and arg.annotation.id in INT_NAMES:
                int_slots[key]['params'].add(arg.arg)
        kind, f.returns = _rewrite(f.returns)
        if kind == 'bool':
            info.fns.add(key)
        elif kind in ('list', 'dict'):
            info.list_fns.add(key)
            if kind == 'dict':
                info.dict_fns.add(key)
        elif isinstance(f.returns, ast.Name) and f.returns.id in INT_NAMES:
            int_slots[key]['ret'] = True
        for node in _own_nodes(f):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                kind, node.annotation = _rewrite(node.annotation)
                if kind:
                    (names if kind == 'bool' else lists).add(node.target.id)
                    if kind == 'dict':
                        lists.add(_mark(node.target.id))
                    annotated.add(node.target.id)
                elif isinstance(node.annotation, ast.Name) and node.annotation.id in INT_NAMES:
                    int_slots[key]['locals'].add(node.target.id)
        declared[key] = (names, lists, annotated)
    class_fields = _class_fields(classes, methods)
    facts = {key: _facts(f) for key, f, owner in units}
    env = _infer(info, tree, units, classes, methods, functions, declared, slots, class_fields,
                 facts, module_bools)
    info.env = env
    info.units = [(key, f) for key, f, owner in units]
    names_of, lists_of = {}, {}
    for key, f, owner in units:
        fixed_names, fixed_lists, annotated = declared[key]
        params = {a.arg for a in (*f.args.posonlyargs, *f.args.args, *f.args.kwonlyargs)}
        gbools = set(module_bools) - params
        fixed_names = set(fixed_names) | gbools
        values, loops, poisoned, breaks, poison_at = facts[key]
        names, lists = _scope(env, f, declared[key], (), (), module_bools, facts[key])
        names_of[key], lists_of[key] = names, lists
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
        for n in sorted(gbools):
            for v in values.get(n, ()):
                if not boolish(v, env, names, lists):
                    _refuse(error, 'the module variable `%s`' % n, v, _hint(v))
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
        for n in _real(fixed_lists):
            for v in values.get(n, ()):
                if not (_vacuous(v) or bool_list_value(v, env, names, lists)):
                    _refuse(error, '`%s` (list[bool])' % n, v,
                            'build it from bools: `[False] * n`, `[x > 0 for x in xs]`')
            for brk in breaks.get(n, ()):
                if brk is None:
                    _fail(error, '`%s` is declared list[bool]; an augmented assignment stores a '
                          'number into it -- assign a bool: `%s[i] = not %s[i]`' % (n, n, n),
                          poison_at.get(n, f))
                if isinstance(brk, tuple):
                    if brk[1] is None or not (_vacuous(brk[1]) or bool_list_value(brk[1], env, names, lists)):
                        _fail(error, '`%s` is declared list[bool]; extend it with a list of bools'
                              % n, brk[1] if brk[1] is not None else f)
                elif not boolish(brk, env, names, lists):
                    _refuse(error, 'every element of `%s`' % n, brk, _hint(brk))
        # a local that holds a bool in some places and a number in others, and is printed
        observed = None
        for n in sorted(set(values) - fixed_names - fixed_lists if _python_surface() else ()):
            vs = values[n]
            if n in names or n in lists or len(vs) < 1:
                continue
            flags = [boolish(v, env, names, lists) for v in vs]
            if any(flags):
                if observed is None:
                    observed = _observed_names(f)
                if n in observed:
                    at = next((v for v, fl in zip(vs, flags) if not fl), vs[0])
                    _fail(error, '`%s` holds a bool in some places and a number in others, and is '
                          'printed; Python keeps each value\'s own type (True / 1).\n'
                          '  write instead: use a bool everywhere (`not` / a comparison) or `int(...)` '
                          'everywhere' % n, at)
        for n, brks in sorted(breaks.items() if _python_surface() else ()):
            if n in lists or n in names or n in fixed_lists or n in params:
                continue
            for brk in brks:
                if brk is not None and not isinstance(brk, tuple) and boolish(brk, env, names, lists):
                    _fail(error, '`%s` is a list or dict that gets the bool `%s` among other values; '
                          'Python keeps each element\'s own type (True / 1).\n'
                          '  write instead: store bools only, or `int(...)` every element' % (n, _show(brk)), brk)
        for node in _own_nodes(f):
            _check_stores(node, env, names, lists, info, classes, methods, slots, error)
    int_params = {}
    for key, f, owner in (units if _python_surface() else ()):
        off = 1 if owner else 0
        int_params[key] = [(i, a.arg) for i, a in enumerate(f.args.args[off:])
                           if a.arg in int_slots[key]['params']]
    for key, f, owner in (units if _python_surface() else ()):
        _check_int_slots(key, f, int_slots[key], int_params, env, names_of[key], lists_of[key],
                         classes, methods, error)
    _mixed_literals(units, tree, env, names_of, lists_of, error)
    return info


def _check_int_slots(key, f, slot, int_params, env, names, lists, classes, methods, error):
    """A bool stored into a slot the program declares int: Python keeps the bool, an int64 prints 1."""
    for node in _own_nodes(f):
        if slot['ret'] and isinstance(node, ast.Return) and node.value is not None \
                and boolish(node.value, env, names, lists):
            _fail(error, 'the result of %s() is declared int, but `%s` is a bool (Python would keep the '
                  'bool and print True / False).\n  write instead: `-> bool`, or `int(%s)`'
                  % (f.name, _show(node.value), _show(node.value)), node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id in slot['locals'] and node.value is not None \
                and boolish(node.value, env, names, lists):
            _fail(error, '`%s` is declared int, but `%s` is a bool (Python would keep the bool and print '
                  'True / False).\n  write instead: `%s: bool`, or `int(%s)`'
                  % (node.target.id, _show(node.value), node.target.id, _show(node.value)), node.value)
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in classes:
            tkey = fn.id + '.__init__'
        elif isinstance(fn, ast.Name):
            tkey = fn.id
        elif isinstance(fn, ast.Attribute):
            owners = [c for c in classes if fn.attr in methods[c]]
            tkey = '%s__%s' % (owners[0], fn.attr) if len(owners) == 1 else None
        else:
            tkey = None
        for index, name in int_params.get(tkey, ()):
            value = (node.args[index] if index < len(node.args)
                     else next((k.value for k in node.keywords if k.arg == name), None))
            if value is not None and boolish(value, env, names, lists):
                _fail(error, 'parameter `%s` of %s() is declared int, but `%s` is a bool (Python would '
                      'keep the bool and print True / False).\n  write instead: declare it `bool`, or '
                      'pass `int(%s)`' % (name, tkey.replace('.__init__', '').replace('__', '.'),
                                          _show(value), _show(value)), value)


def check_numeric_vars(info, variables, bools, error):
    """A module variable that starts as a number must not be assigned a bool: Python would then
    print it as True / False, and the variable is one int64 that prints as a number."""
    if info.env is None:
        if bools:
            _fail(error, 'a bool module variable needs the compiler\'s own bool; this program defines a '
                  'struct named bool', ast.Pass())
        return
    for key, f in info.units:
        names, lists = set(info.locals[key]) | set(bools), set(info.lists[key])
        for node in _own_nodes(f):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in variables and name not in bools and boolish(node.value, info.env, names, lists):
                    _fail(error, 'the module variable `%s` starts as a number and is assigned a bool (`%s`); '
                          'Python would then print it as True / False.\n'
                          '  write instead: start it as False / True, or store a number '
                          '(`int(%s)`)' % (name, _show(node.value), _show(node.value)), node)


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
                    and not (_vacuous(node.value) or bool_list_value(node.value, env, names, lists))):
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
            if not bool_list_value(value, env, names, lists) and not _vacuous(value):
                _refuse(error, what(name) + ' (list[bool])', value,
                        'pass a list of bools (`[False] * n`, a list[bool] local)')
        elif not boolish(value, env, names, lists):
            _refuse(error, what(name), value, _hint(value))
