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
    """True only when `text` really uses `export` from ail_ffi.

    A mere import, or the word `export` in a string or identifier, does not count: this decides
    whether `lower()` validates a normal build, and an unrelated `@extern` program that happens to
    contain the word must keep building exactly as before.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    export_names, module_names, star = set(), set(), False
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == 'ail_ffi' and node.level == 0:
            for alias in node.names:
                if alias.name == 'export':
                    export_names.add(alias.asname or alias.name)
                elif alias.name == '*':
                    star = True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'ail_ffi':
                    module_names.add(alias.asname or alias.name)
    if star:
        export_names.add('export')

    def is_export_ref(node):
        return (_is_name(node, export_names)
                or (isinstance(node, ast.Attribute) and node.attr == 'export'
                    and _is_name(node.value, module_names)))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_export_ref(node.func):
            return True
        for decorator in getattr(node, 'decorator_list', ()):
            if isinstance(decorator, ast.Call) and not decorator.args and not decorator.keywords:
                decorator = decorator.func
            if is_export_ref(decorator):
                return True
    return False


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
