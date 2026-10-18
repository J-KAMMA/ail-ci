"""Top-level user definitions that shadow a built-in name, resolved with Python's scoping.

`fn abs(x: int) -> int { ... }` followed by `abs(2)` must call the user's `abs`, exactly as CPython
does. The compiler dispatches dozens of built-ins by name (`f == 'abs'`, the heapq/bisect lowering,
sort keys, nested-list and bool scans, the general path), so instead of teaching every one of those
sites to consult the user's names, `rename` gives each shadowing module-level definition a fresh
identifier (`py_abs`) BEFORE any pass sees the source. Only references that Python would resolve to
that module-level binding are renamed: a parameter, local, comprehension variable or struct field
named `abs` keeps its name, and attribute/method names are never touched. The source is edited in
place token by token, so every line number (and therefore every diagnostic) stays where it was.

A definition whose name is also a type or a structural form the compiler cannot give up (a function
named `int`, `str`, `list`, an exception name, `par_range`, ...) is refused with the line and a
rename suggestion as soon as the program reads that name outside an annotation; it is never
silently compiled against the built-in. (Such a function that nothing calls stays as it was.)
"""
import ast
import builtins
import re

# AIL's own built-in functions (ail_builtin_api.DECLARATIONS / ail_builtin_syntax_forms plain names
# plus the intrinsics the typed path dispatches by name). test_ail_builtin_shadowing checks that
# every declared plain builtin is listed here.
AIL_BUILTINS = frozenset('''
    heappush heappop heapify heappushpop heapreplace bisect bisect_left bisect_right
    insort insort_left insort_right
    read_stdin_bytes read_bytes write_bytes append_bytes write_text write_stdout_bytes flush_stdout
    open_binary get_env current_dir list_dir path_exists is_dir file_size same_file make_dir
    remove_dir remove_file replace_path monotonic_ms tcp_connect tcp_listen tcp_poll
    wrapping_add wrapping_sub wrapping_mul integer_encode integer_decode float64_encode
    float64_decode pcm16_scale_le jscharat jsdiv jsnegzero
'''.split())

PY_BUILTINS = frozenset(name for name in dir(builtins)
                        if not name.startswith('_') and name[:1].islower())

# Names that are also a type (annotations name the built-in type) or that the front end emits
# structurally; a definition with one of these names cannot be honoured without changing what the
# rest of the program means.
_CORE_TYPES = frozenset('int float str bool bytes list dict set tuple frozenset '
                        'exception Callable Optional'.split())
# A struct may carry one of these names (the compiler already lets a struct named `bytearray` be
# the annotated type); a function or constant may not, since annotations keep naming the builtin.
_VALUE_TYPES = frozenset('bytearray binaryfile tcpsocket'.split())
_STRUCTURAL = {
    'par_range': '`parallel for` is lowered to a par_range call',
    'math': 'math.* functions are reached through this name',
    'sys': 'sys.argv/sys.stdin are reached through this name',
    'os': 'os.* functions are reached through this name',
}
_EXCEPTIONS = frozenset(name for name in dir(builtins)
                        if isinstance(getattr(builtins, name), type)
                        and issubclass(getattr(builtins, name), BaseException))

SHADOWABLE = (PY_BUILTINS | AIL_BUILTINS | _VALUE_TYPES) - _CORE_TYPES - set(_STRUCTURAL)


# A cheap pre-filter: module-level `def`/`class` names and `NAME =` / `NAME: T =` heads.
_HEAD = re.compile(r'^\s*(?:async\s+)?(?:def|class)\s+(\w+)|^(\w+)\s*(?::[^=\n]*)?=', re.M)


def _suggest(name):
    return 'my_' + name


def _refusal(Unsupported, kind, name, line, why):
    error = Unsupported("%s '%s' shadows the built-in %s %s; %s, so it cannot be redefined -- "
                        "rename it (e.g. '%s')" % (kind, name, 'type' if name in _CORE_TYPES | _VALUE_TYPES
                                                   else 'exception' if name in _EXCEPTIONS
                                                   else 'name', name, why, _suggest(name)))
    error.source_line = line
    return error


def _top_level(tree):
    """[(name, kind, node)] for every module-level binding: functions, structs, constants."""
    found = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.append((node.name, 'function', node))
        elif isinstance(node, ast.ClassDef):
            found.append((node.name, 'struct', node))
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for leaf in ast.walk(target):
                    if isinstance(leaf, ast.Name):
                        found.append((leaf.id, 'constant', node))
    return found


def _value_uses(tree):
    """Names read anywhere outside an annotation (annotations keep naming the built-in type)."""
    annotations = set()
    for node in ast.walk(tree):
        parts = []
        if isinstance(node, ast.arg):
            parts.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            parts.append(node.annotation)
        for part in parts:
            if part is not None:
                annotations.update(id(n) for n in ast.walk(part))
    return {node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and id(node) not in annotations}


def _check(found, Unsupported, tree):
    uses = None
    for name, kind, node in found:
        if name not in _CORE_TYPES | _EXCEPTIONS | _VALUE_TYPES | set(_STRUCTURAL):
            continue
        if kind == 'struct' and name == 'exception':
            continue   # the struct pass refuses it as 'reserved class name: exception'
        if kind != 'struct':
            # A function or constant nothing reads (outside annotations) shadows nothing.
            if uses is None:
                uses = _value_uses(tree)
            if name not in uses:
                continue
        if kind == 'struct':
            # A struct's own lines carry no AIL position (the front end maps statements inside
            # functions), so a refusal points at the first statement that uses the struct.
            lines = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name
                     and n.lineno > node.end_lineno]
            node = type('At', (), {'lineno': min(lines) if lines else node.lineno})
        if name in _CORE_TYPES:
            raise _refusal(Unsupported, 'AIL ' + kind, name, node.lineno,
                           'annotations use %s as a type' % name)
        if name in _EXCEPTIONS:
            raise _refusal(Unsupported, 'AIL ' + kind, name, node.lineno,
                           'raise/except name the built-in exception')
        if name in _STRUCTURAL:
            raise _refusal(Unsupported, 'AIL ' + kind, name, node.lineno, _STRUCTURAL[name])
        if name in _VALUE_TYPES and kind != 'struct':
            raise _refusal(Unsupported, 'AIL ' + kind, name, node.lineno,
                           'annotations use %s as a type' % name)


def _bound_names(body, params=()):
    """Names a function/lambda body binds locally (Python's compile-time rule), minus `global`s."""
    bound, declared_global = set(params), set()
    stack = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Global):
            declared_global.update(node.names)
            continue
        if isinstance(node, ast.Nonlocal):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
            stack.extend(node.decorator_list)
            if not isinstance(node, ast.ClassDef):
                stack.extend(d for d in node.args.defaults + node.args.kw_defaults if d is not None)
            continue
        if isinstance(node, ast.Lambda):
            stack.extend(node.args.defaults)
            continue
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            stack.append(node.generators[0].iter)
            # walrus targets inside a comprehension bind in the enclosing function
            stack.extend(n for n in ast.walk(node) if isinstance(n, ast.NamedExpr))
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.alias):
            bound.add((node.asname or node.name).split('.')[0])
        elif isinstance(node, ast.MatchAs) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            bound.add(node.name)
        stack.extend(ast.iter_child_nodes(node))
    return bound - declared_global


def _params(args):
    return [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs
            + ([args.vararg] if args.vararg else []) + ([args.kwarg] if args.kwarg else [])]


class _Collector:
    """Every ast.Name that Python resolves to a module-level binding in `targets`."""

    def __init__(self, targets, Unsupported):
        self.targets = targets
        self.Unsupported = Unsupported
        self.names = []

    def visit(self, node, chain, class_locals=None):
        if isinstance(node, ast.Name):
            if (node.id in self.targets and not any(node.id in scope for scope in chain)
                    and not (class_locals is not None and node.id in class_locals)):
                self.names.append(node)
            return
        if isinstance(node, ast.Global):
            hit = self.targets.intersection(node.names)
            if hit:
                raise _refusal(self.Unsupported, 'global statement for', min(hit), node.lineno,
                               'a global declaration of it is not supported')
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for item in node.decorator_list + node.args.defaults + [d for d in node.args.kw_defaults if d]:
                self.visit(item, chain, class_locals)
            for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs + [
                    node.args.vararg, node.args.kwarg]:
                if arg is not None and arg.annotation is not None:
                    self.visit(arg.annotation, chain, class_locals)
            if node.returns is not None:
                self.visit(node.returns, chain, class_locals)
            scope = _bound_names(node.body, _params(node.args))
            for statement in node.body:
                self.visit(statement, chain + [scope])
            return
        if isinstance(node, ast.Lambda):
            for item in node.args.defaults:
                self.visit(item, chain, class_locals)
            self.visit(node.body, chain + [_bound_names([node.body], _params(node.args))])
            return
        if isinstance(node, ast.ClassDef):
            for item in node.decorator_list + node.bases + [k.value for k in node.keywords]:
                self.visit(item, chain, class_locals)
            local = _bound_names(node.body)
            for statement in node.body:
                self.visit(statement, chain, local)
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            self.visit(node.generators[0].iter, chain, class_locals)
            scope = set()
            for generator in node.generators:
                scope.update(n.id for n in ast.walk(generator.target) if isinstance(n, ast.Name))
            inner = chain + [scope]
            for index, generator in enumerate(node.generators):
                self.visit(generator.target, inner)
                if index:
                    self.visit(generator.iter, inner)
                for condition in generator.ifs:
                    self.visit(condition, inner)
            for part in ((node.key, node.value) if isinstance(node, ast.DictComp) else (node.elt,)):
                self.visit(part, inner)
            return
        for child in ast.iter_child_nodes(node):
            self.visit(child, chain, class_locals)


def rename(source, Unsupported, extra_names=()):
    """(source, {new: old}): `source` with every module-level definition that shadows a built-in
    (and every reference Python resolves to it) renamed to a fresh identifier. `extra_names` are
    names bound outside this source (linked objects) that the source may reference as globals.
    A source with no such definition is returned unchanged (the same string object)."""
    watched = SHADOWABLE | _CORE_TYPES | _EXCEPTIONS | set(_STRUCTURAL)
    heads = {a or b for a, b in _HEAD.findall(source)}
    if not heads & watched and not watched.intersection(extra_names):
        return source, {}
    stripped = source.strip()
    try:
        tree = ast.parse(stripped)
    except SyntaxError:
        return source, {}
    found = _top_level(tree)
    _check(found, Unsupported, tree)
    targets = {name for name, _, _ in found if name in SHADOWABLE}
    targets.update(name for name in extra_names if name in SHADOWABLE)
    if not targets:
        return source, {}
    used = set(re.findall(r'\w+', source))
    fresh = {}
    for name in sorted(targets):
        candidate, number = 'py_' + name, 2
        while candidate in used:
            candidate, number = 'py_%s_%d' % (name, number), number + 1
        used.add(candidate)
        fresh[name] = candidate
    collector = _Collector(set(targets), Unsupported)
    for statement in tree.body:
        collector.visit(statement, [])
    lines = stripped.split('\n')
    encoded = [line.encode('utf8') for line in lines]
    edits = {}   # line index -> [(byte column, old, new)]

    def edit(lineno, column, old, new):
        if encoded[lineno - 1][column:column + len(old.encode('utf8'))] != old.encode('utf8'):
            raise _refusal(Unsupported, 'definition', old, lineno,
                           'its uses could not be located in the source')
        edits.setdefault(lineno - 1, []).append((column, old, new))

    for name, kind, node in found:
        if name in fresh and kind in ('function', 'struct'):
            line = encoded[node.lineno - 1]
            match = re.compile(rb'(?:async\s+)?(?:def|class)\s+(%s)\b' % re.escape(name.encode())).match(
                line, node.col_offset)
            if match is None:
                raise _refusal(Unsupported, 'AIL ' + kind, name, node.lineno,
                               'its definition could not be located in the source')
            edit(node.lineno, match.start(1), name, fresh[name])
    for node in collector.names:
        edit(node.lineno, node.col_offset, node.id, fresh[node.id])
    # A struct used as a declared return type is spelled `__ail_checked_<name>__` by the front end.
    checked = {'__ail_checked_%s__' % old: '__ail_checked_%s__' % new for old, new in fresh.items()}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in checked:
            edit(node.lineno, node.col_offset, node.id, checked[node.id])
    for index, changes in edits.items():
        line = encoded[index]
        for column, old, new in sorted(set(changes), reverse=True):
            line = line[:column] + new.encode('utf8') + line[column + len(old.encode('utf8')):]
        lines[index] = line.decode('utf8')
    start = source.find(stripped)
    renamed = source[:start] + '\n'.join(lines) + source[start + len(stripped):]
    return renamed, {new: old for old, new in fresh.items()}


def rename_all(source, Unsupported, extra_names=()):
    """Comprehension variables that could clash with the enclosing scope get fresh names
    (compscope.py), then shadowing definitions are renamed (below); one {fresh: old} map covers both."""
    try:
        import compscope
    except ImportError:         # loaded by file path (a test), not as part of the package directory
        import importlib.util
        import os
        spec = importlib.util.spec_from_file_location(
            'compscope', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'compscope.py'))
        compscope = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compscope)
    source, scoped = compscope.rename(source)
    source, mapping = rename(source, Unsupported, extra_names)
    if scoped:
        mapping = dict(scoped, **mapping)
    return source, mapping


def restore_text(text, mapping):
    """`text` with every fresh identifier from `rename` spelled as the user wrote it."""
    if not mapping or not isinstance(text, str):
        return text
    for new, old in mapping.items():
        text = re.sub(r'\b%s\b' % re.escape(new), old, text)
    return text


def restore_error(error, mapping):
    """Rewrite a refusal raised on renamed source so it names the user's own identifiers."""
    if not mapping:
        return
    if error.args and isinstance(error.args[0], str):
        error.args = (restore_text(error.args[0], mapping),) + error.args[1:]
    for attribute in ('source_function', 'repair_hint'):
        value = getattr(error, attribute, None)
        if isinstance(value, str):
            setattr(error, attribute, restore_text(value, mapping))
    details = getattr(error, 'type_details', None)
    if isinstance(details, dict):
        error.type_details = {key: restore_text(value, mapping) for key, value in details.items()}
