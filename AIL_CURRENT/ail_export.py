"""Front end of `ail build --lib NAME prog.py`: read the @export functions of a Python-syntax file.

    from dataclasses import dataclass
    from ail_ffi import export

    @dataclass
    class Point:
        x: float
        y: float
        visible: bool

    @export
    def length(p: Point) -> float: ...

`lower(text)` removes the CPython-only parts of the file (the ail_ffi and dataclasses imports, the
@export and @dataclass decorators, `if __name__ == "__main__":` blocks), turns every dataclass into a
plain `__init__` class, and appends one wrapper per exported function whose parameters and result are
only the scalar kinds the C library core carries (int, float, str, bytes, list[int], list[float]; a
bool travels as an int and a dataclass as one scalar per field). It returns that text and a manifest
that python/pkg-v12/c_export.py turns into the C header and the shared and static libraries. A file
without @export is not touched by this module.
"""
import ast

SCALARS = ('int', 'float', 'bool', 'str', 'bytes')
CORE_TYPE = {'int': 'int', 'float': 'float', 'bool': 'int', 'str': 'str', 'bytes': 'bytes',
             'ints': 'list[int]', 'floats': 'list[float]'}
WRAPPER_PREFIX = 'ailx_'
RESERVED_C = ('free', 'last_error')


class ExportError(ValueError):
    pass


def uses_export(text):
    return '@' in text and 'export' in text and 'ail_ffi' in text


def _kind(annotation, structs, *, result, where):
    if isinstance(annotation, ast.Constant) and annotation.value is None:
        if result:
            return {'kind': 'void'}
    elif isinstance(annotation, ast.Name):
        if annotation.id in SCALARS:
            return {'kind': annotation.id}
        if annotation.id in structs and not result:
            return {'kind': 'struct', 'type': annotation.id}
        if annotation.id in structs:
            raise ExportError('%s: a dataclass cannot be returned; return its fields or take it by pointer in a '
                              'void function (C results are scalars, str, bytes or numeric lists)' % where)
    elif (isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name)
          and annotation.value.id == 'list' and isinstance(annotation.slice, ast.Name)
          and annotation.slice.id in ('int', 'float')):
        return {'kind': 'ints' if annotation.slice.id == 'int' else 'floats'}
    raise ExportError('%s: unsupported type %s (allowed: int float bool str bytes list[int] list[float]%s)' % (
        where, ast.unparse(annotation), ', None' if result else ' and dataclasses of int/float/bool'))


def _is_name(node, names):
    return isinstance(node, ast.Name) and node.id in names


def lower(text, library_name=None):
    """(text for the library core, manifest). Raises ExportError."""
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise ExportError('@export needs Python syntax: %s' % error) from error
    export_names, module_names, dataclass_names, dataclasses_modules = set(), set(), set(), set()
    body = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue          # the module docstring
        if isinstance(node, ast.ImportFrom) and node.module == 'ail_ffi' and node.level == 0:
            for alias in node.names:
                if alias.name != 'export':
                    raise ExportError('C libraries use only `export` from ail_ffi, not %s' % alias.name)
                export_names.add(alias.asname or alias.name)
            continue
        if isinstance(node, ast.Import) and all(alias.name in ('ail_ffi', 'dataclasses') for alias in node.names):
            for alias in node.names:
                (module_names if alias.name == 'ail_ffi' else dataclasses_modules).add(alias.asname or alias.name)
            continue
        if isinstance(node, ast.ImportFrom) and node.module == 'dataclasses' and node.level == 0:
            for alias in node.names:
                if alias.name != 'dataclass':
                    raise ExportError('only `dataclass` is used from dataclasses, not %s' % alias.name)
                dataclass_names.add(alias.asname or alias.name)
            continue
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
                and node.test.left.id == '__name__' and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Constant) and node.test.comparators[0].value == '__main__'):
            continue          # demo code for CPython; the library has no main
        body.append(node)

    def decorated_with(node, check):
        return [d for d in node.decorator_list if check(d)]

    def is_export(d):
        d = d.func if isinstance(d, ast.Call) and not d.args and not d.keywords else d
        return _is_name(d, export_names) or (isinstance(d, ast.Attribute) and d.attr == 'export'
                                             and _is_name(d.value, module_names))

    def is_dataclass(d):
        return _is_name(d, dataclass_names) or (isinstance(d, ast.Attribute) and d.attr == 'dataclass'
                                                and _is_name(d.value, dataclasses_modules))

    structs, classes = {}, []
    for node in body:
        if not isinstance(node, ast.ClassDef):
            continue
        marks = decorated_with(node, is_dataclass)
        if not marks:
            if node.decorator_list:
                raise ExportError('class %s: decorators other than @dataclass are not supported' % node.name)
            continue
        if len(marks) != len(node.decorator_list) or node.bases or node.keywords:
            raise ExportError('dataclass %s: a plain @dataclass without bases or options only' % node.name)
        fields = []
        for statement in node.body:
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) or isinstance(statement, ast.Pass):
                continue
            if (not isinstance(statement, ast.AnnAssign) or statement.value is not None
                    or not isinstance(statement.target, ast.Name)
                    or not isinstance(statement.annotation, ast.Name)
                    or statement.annotation.id not in ('int', 'float', 'bool')):
                raise ExportError('dataclass %s: fields are `name: int|float|bool` without defaults or methods' % node.name)
            fields.append({'name': statement.target.id, 'kind': statement.annotation.id})
        if not fields:
            raise ExportError('dataclass %s has no fields' % node.name)
        structs[node.name] = fields
        classes.append(node)

    exports, lowered, taken = [], [], set()
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            taken.add(node.name)
    for node in body:
        if isinstance(node, ast.ClassDef) and node.name in structs:
            fields = structs[node.name]
            init = 'class %s:\n    def __init__(self%s):\n%s\n' % (
                node.name, ''.join(', %s: %s' % (f['name'], f['kind']) for f in fields),
                '\n'.join('        self.%s = %s' % (f['name'], f['name']) for f in fields))
            lowered.append(ast.parse(init).body[0])
            continue
        if isinstance(node, ast.FunctionDef):
            marks = decorated_with(node, is_export)
            if marks:
                if len(marks) != len(node.decorator_list):
                    raise ExportError('%s: only @export may decorate an exported function' % node.name)
                node.decorator_list = []
                exports.append(node)
        lowered.append(node)
    if not exports:
        raise ExportError('no @export function found: mark each function of the C API with @export '
                          '(from ail_ffi import export)')
    manifest_exports, wrappers = [], []
    for fn in exports:
        where = 'function %s' % fn.name
        if fn.name in RESERVED_C or fn.name.startswith('_') or not fn.name.isascii():
            raise ExportError('%s: the name is reserved (%s) or not a plain ASCII public name' % (where, ', '.join(RESERVED_C)))
        a = fn.args
        if a.defaults or a.kw_defaults or a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg:
            raise ExportError('%s: plain parameters without defaults only' % where)
        if fn.returns is None:
            raise ExportError('%s: annotate the result (-> None for no result)' % where)
        params = []
        for index, arg in enumerate(a.args):
            if arg.annotation is None:
                raise ExportError('%s: parameter %s needs a type annotation' % (where, arg.arg))
            kind = _kind(arg.annotation, structs, result=False, where='%s, parameter %s' % (where, arg.arg))
            params.append(dict(kind, name=arg.arg))
        result = _kind(fn.returns, structs, result=True, where=where + ', result')
        wrapper = WRAPPER_PREFIX + fn.name
        if wrapper in taken:
            raise ExportError('%s: the name %s is reserved for the generated C wrapper' % (where, wrapper))
        taken.add(wrapper)
        declared, call = [], []
        for index, p in enumerate(params):
            n = 'a%d' % index
            if p['kind'] == 'struct':
                fields = structs[p['type']]
                for f in fields:
                    declared.append('%s_%s: %s' % (n, f['name'], CORE_TYPE[f['kind']]))
                call.append('%s(%s)' % (p['type'], ', '.join(
                    '%s_%s%s' % (n, f['name'], ' != 0' if f['kind'] == 'bool' else '') for f in fields)))
            else:
                declared.append('%s: %s' % (n, CORE_TYPE[p['kind']]))
                call.append(n + (' != 0' if p['kind'] == 'bool' else ''))
        expression = '%s(%s)' % (fn.name, ', '.join(call))
        if result['kind'] == 'void':
            source = 'def %s(%s) -> None:\n    %s\n' % (wrapper, ', '.join(declared), expression)
        elif result['kind'] == 'bool':
            source = ('def %s(%s) -> int:\n    value = %s\n    if value:\n        return 1\n    return 0\n'
                      % (wrapper, ', '.join(declared), expression))
        else:
            source = 'def %s(%s) -> %s:\n    return %s\n' % (wrapper, ', '.join(declared), CORE_TYPE[result['kind']], expression)
        wrappers.append(ast.parse(source).body[0])
        manifest_exports.append({'name': fn.name, 'wrapper': wrapper, 'params': params, 'result': result})
    tree.body = [*lowered, *wrappers]
    internal = sorted(n.name for n in lowered if isinstance(n, (ast.FunctionDef, ast.ClassDef)))
    manifest = {'schema': 1, 'exports': manifest_exports, 'structs': structs, 'internal': internal}
    return ast.unparse(ast.fix_missing_locations(tree)) + '\n', manifest


def _export_decorators(tree):
    """The decorator nodes this file binds to ail_ffi.export, from its top-level imports."""
    export_names, module_names = set(), set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == 'ail_ffi' and node.level == 0:
            for alias in node.names:
                if alias.name == '*':
                    export_names.add('export')
                elif alias.name == 'export':
                    export_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'ail_ffi':
                    module_names.add(alias.asname or alias.name)
    found = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if (_is_name(target, export_names)
                    or (isinstance(target, ast.Attribute) and target.attr == 'export'
                        and _is_name(target.value, module_names))):
                found.append(decorator)
    return found


_BUILTIN_TYPES = {'int': ('type', 'int'), 'float': ('type', 'float'), 'bool': ('type', 'bool'),
                  'str': ('type', 'str'), 'bytes': ('type', 'bytes'), 'list': ('type', 'list')}


def _env_lookup(name, env):
    if name in env:
        return env[name]
    if name in _BUILTIN_TYPES:
        return _BUILTIN_TYPES[name]
    import builtins
    if hasattr(builtins, name):
        return ('object', name)
    return ('unbound', name)


def _decorator_target(decorator):
    return decorator.func if isinstance(decorator, ast.Call) else decorator


def _resolve_value(node, env):
    """A symbolic value for one module-level expression, enough to resolve export annotations."""
    if isinstance(node, ast.Name):
        return _env_lookup(node.id, env)
    if isinstance(node, ast.Constant):
        if node.value is None:
            return ('none',)
        if isinstance(node.value, str):
            return ('string', node.value)
        return ('object', ast.unparse(node))
    if isinstance(node, ast.Subscript):
        base = _resolve_value(node.value, env)
        if base == ('type', 'list'):
            element = node.slice
            if isinstance(element, ast.Tuple) and len(element.elts) == 1:
                element = element.elts[0]
            if isinstance(element, ast.Name):
                return ('list', _env_lookup(element.id, env))
        return ('object', 'subscript')
    if isinstance(node, ast.Attribute):
        base = _resolve_value(node.value, env)
        if base == ('module', 'dataclasses') and node.attr == 'dataclass':
            return ('marker', 'dataclass')
        if base == ('module', 'ail_ffi') and node.attr == 'export':
            return ('marker', 'export')
        return ('object', 'attribute')
    if isinstance(node, ast.BinOp):
        return ('object', 'union')
    return ('object', 'expression')


def _deref(value, env, depth=0):
    """Follow a string annotation as CPython's typing.get_type_hints does."""
    if value[0] == 'string' and depth < 8:
        try:
            expression = ast.parse(value[1], mode='eval').body
        except SyntaxError:
            return ('object', 'forward reference')
        return _deref(_resolve_value(expression, env), env, depth + 1)
    return value


def _hint_ok(value, *, result):
    if value[0] == 'none':
        return result
    if value[0] == 'type':
        return value[1] in SCALARS
    if value[0] == 'list':
        return value[1] in (('type', 'int'), ('type', 'float'))
    if value[0] == 'dataclass':
        if result:
            return False
        return all(field[0] == 'type' and field[1] in ('int', 'float', 'bool')
                   for field in value[2])
    return False


def _describe(value):
    if value[0] == 'type':
        return value[1]
    if value[0] == 'list':
        return 'list[%s]' % _describe(value[1])
    if value[0] == 'dataclass':
        return 'dataclass %s' % value[1]
    if value[0] == 'string':
        return repr(value[1])
    if value[0] == 'none':
        return 'None'
    if value[0] == 'unbound':
        return 'name %r' % value[1]
    return str(value[1])


def _hint_problem(value):
    if value[0] == 'unbound':
        return "NameError: name %r is not defined (CPython resolves annotations when @export runs)" % value[1]
    if value[0] == 'dataclass':
        return 'TypeError: a dataclass is only allowed as a parameter whose fields are int, float or bool'
    return 'TypeError: %s is not one of int float bool str bytes list[int] list[float]' % _describe(value)


def _bind_target(target, value, env):
    if isinstance(target, ast.Name):
        env[target.id] = value
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            if isinstance(element, ast.Starred):
                element = element.value
            _bind_target(element, ('object', 'unpacked'), env)


def _merge_envs(first, second):
    merged = {}
    for name in set(first) | set(second):
        a, b = first.get(name), second.get(name)
        merged[name] = a if a == b else ('object', 'conditional')
    return merged


def _walk_environment(statements, env, exported, future):
    """Run the top-level statements over the symbolic module namespace, validating @export defs."""
    for node in statements:
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            if any(alias.name == 'annotations' for alias in node.names):
                future = True
            continue
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == '*':
                    continue
                name = alias.asname or alias.name
                if node.module == 'dataclasses' and alias.name == 'dataclass':
                    env[name] = ('marker', 'dataclass')
                elif node.module == 'ail_ffi' and alias.name == 'export':
                    env[name] = ('marker', 'export')
                elif node.module == 'ail_ffi' and alias.name == 'exports':
                    env[name] = ('object', 'exports')
                else:
                    env[name] = ('object', '%s.%s' % (node.module, alias.name))
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                top = alias.name.split('.')[0]
                if top == 'dataclasses':
                    env[name] = ('module', 'dataclasses')
                elif top == 'ail_ffi':
                    env[name] = ('module', 'ail_ffi')
                else:
                    env[name] = ('module', top)
            continue
        if isinstance(node, ast.ClassDef):
            dataclass = any(_resolve_value(_decorator_target(d), env) == ('marker', 'dataclass')
                            for d in node.decorator_list)
            if dataclass:
                fields = []
                for statement in node.body:
                    if (isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
                            and statement.annotation is not None):
                        fields.append(('string', ast.unparse(statement.annotation)) if future
                                      else _resolve_value(statement.annotation, env))
                env[node.name] = ('dataclass', node.name, fields)
            else:
                env[node.name] = ('class', node.name)
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(id(d) in exported for d in node.decorator_list):
                _validate_export(node, env)
            env[node.name] = ('function', node.name)
            continue
        if isinstance(node, ast.Assign):
            value = _resolve_value(node.value, env)
            for target in node.targets:
                _bind_target(target, value, env)
            continue
        if isinstance(node, ast.AnnAssign):
            value = _resolve_value(node.value, env) if node.value is not None else ('object', 'annotation')
            _bind_target(node.target, value, env)
            continue
        if isinstance(node, ast.AugAssign):
            _bind_target(node.target, ('object', 'augmented'), env)
            continue
        if isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    env.pop(target.id, None)
            continue
        if isinstance(node, ast.If):
            body = _walk_environment(node.body, dict(env), exported, future)
            other = _walk_environment(node.orelse, dict(env), exported, future)
            env.clear()
            env.update(_merge_envs(body, other))
            continue
        if isinstance(node, (ast.For, ast.AsyncFor)):
            base = dict(env)
            loop = dict(env)
            _bind_target(node.target, ('object', 'loop'), loop)
            loop = _walk_environment(node.body, loop, exported, future)
            env.clear()
            env.update(_merge_envs(base, loop))
            _walk_environment(node.orelse, env, exported, future)
            continue
        if isinstance(node, ast.While):
            base = dict(env)
            loop = _walk_environment(node.body, dict(env), exported, future)
            env.clear()
            env.update(_merge_envs(base, loop))
            _walk_environment(node.orelse, env, exported, future)
            continue
        if isinstance(node, ast.Try):
            ends = [_walk_environment(node.body, dict(env), exported, future)]
            for handler in node.handlers:
                branch = dict(env)
                if handler.name:
                    branch[handler.name] = ('object', 'exception')
                ends.append(_walk_environment(handler.body, branch, exported, future))
            merged = ends[0]
            for branch in ends[1:]:
                merged = _merge_envs(merged, branch)
            merged = _walk_environment(node.orelse, merged, exported, future)
            merged = _walk_environment(node.finalbody, merged, exported, future)
            env.clear()
            env.update(merged)
            continue
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    _bind_target(item.optional_vars, ('object', 'with'), env)
            _walk_environment(node.body, env, exported, future)
            continue
    return env


def _validate_export(function, env):
    where = 'function %s' % function.name
    for argument in function.args.args:
        if argument.annotation is None:
            continue
        value = _deref(_resolve_value(argument.annotation, env), env)
        if not _hint_ok(value, result=False):
            raise ExportError('%s, parameter %s: %s' % (where, argument.arg, _hint_problem(value)))
    value = _deref(_resolve_value(function.returns, env), env)
    if not _hint_ok(value, result=True):
        raise ExportError('%s, result: %s' % (where, _hint_problem(value)))


def lower_executable(text):
    """Remove `@export` from a normal executable, after checking it as CPython's decorator does.

    In a library build `lower()` rewrites the decorated functions; in an executable the decorator
    is an identity check, so the definitions stay and only the marker goes. A decorator the
    CPython implementation would reject is refused here by name, never run with different meaning.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    marks = _export_decorators(tree)
    if not marks:
        return text
    lower(text)            # the same signature checks CPython's export() applies at import time
    _walk_environment(tree.body, {}, {id(mark) for mark in marks}, False)
    lines = text.splitlines(keepends=True)
    for decorator in marks:
        for index in range(decorator.lineno - 1, decorator.end_lineno):
            row = lines[index]
            body = row.rstrip('\r\n')
            ending = row[len(body):]
            start = decorator.col_offset if index == decorator.lineno - 1 else 0
            end = decorator.end_col_offset if index == decorator.end_lineno - 1 else len(body)
            if index == decorator.lineno - 1:
                at = start - 1
                while at >= 0 and body[at] in ' \t':
                    at -= 1
                if at >= 0 and body[at] == '@':
                    start = at
            end = min(end, len(body))
            if end < start:
                continue
            lines[index] = body[:start] + ' ' * (end - start) + body[end:] + ending
    return ''.join(lines)
