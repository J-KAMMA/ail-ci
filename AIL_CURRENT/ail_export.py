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


def strip_export_decorators(text):
    """Check CPython's @export rules and remove the decorator before a normal build.

    @export returns the function unchanged after checking its signature, so a normal program that
    runs on CPython behaves as if the decorator were absent.  Removing it also lets the general
    path, which refuses unknown decorators, build the same program.  A signature CPython refuses
    keeps a named refusal instead of compiling with different behaviour."""
    if not uses_export(text):
        return text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    future_annotations = False
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and not node.level and node.module == '__future__':
            future_annotations = future_annotations or any(alias.name == 'annotations' for alias in node.names)

    # Every module-level binding of a decorator name, in source order.  A decorator is the real
    # `ail_ffi.export`/`dataclasses.dataclass` only while the latest binding before it is the
    # matching import; a rebinding or `del` between the import and the decorator shadows the name
    # on CPython, so that spelling is refused by name instead of being stripped.
    bindings = {}
    order = [0]

    def bind(name, line, tag=None):
        bindings.setdefault(name, []).append((line, order[0], tag))
        order[0] += 1

    class Binder(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            bind(node.name, node.lineno)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            bind(node.name, node.lineno)

        def visit_Lambda(self, node):
            pass

        def visit_ListComp(self, node):
            pass

        def visit_SetComp(self, node):
            pass

        def visit_DictComp(self, node):
            pass

        def visit_GeneratorExp(self, node):
            pass

        def visit_Import(self, node):
            for alias in node.names:
                bind(alias.asname or alias.name.split('.')[0], node.lineno, ('import', alias.name))

        def visit_ImportFrom(self, node):
            for alias in node.names:
                bind(alias.asname or alias.name, node.lineno, ('from', node.module, alias.name))

        def visit_Delete(self, node):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bind(target.id, node.lineno)
            self.generic_visit(node)

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                bind(node.id, node.lineno)
            self.generic_visit(node)

    binder = Binder()
    for node in tree.body:
        binder.visit(node)

    def genuine(name, line, tag):
        entries = [entry for entry in bindings.get(name, ()) if entry[0] < line]
        return bool(entries) and max(entries, key=lambda entry: entry[1])[2] == tag

    def shadowed(name, line):
        return any(bound < line for bound, _, _ in bindings.get(name, ()))

    def is_export_name(decorator):
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name):
            return genuine(target.id, decorator.lineno, ('from', 'ail_ffi', 'export'))
        return (isinstance(target, ast.Attribute) and target.attr == 'export'
                and isinstance(target.value, ast.Name)
                and genuine(target.value.id, decorator.lineno, ('import', 'ail_ffi')))

    def is_export(decorator):
        return ((not isinstance(decorator, ast.Call)
                 or (not decorator.args and not decorator.keywords))
                and is_export_name(decorator))

    def is_dataclass(decorator):
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name):
            return genuine(target.id, decorator.lineno, ('from', 'dataclasses', 'dataclass'))
        return (isinstance(target, ast.Attribute) and target.attr == 'dataclass'
                and isinstance(target.value, ast.Name)
                and genuine(target.value.id, decorator.lineno, ('import', 'dataclasses')))

    def imported_names(tag):
        return {name for name, entries in bindings.items()
                if any(entry[2] == tag for entry in entries)}

    export_names = imported_names(('from', 'ail_ffi', 'export'))
    module_names = imported_names(('import', 'ail_ffi'))
    dataclass_names = imported_names(('from', 'dataclasses', 'dataclass'))
    dataclasses_modules = imported_names(('import', 'dataclasses'))

    def rebound_name(decorator):
        """The imported decorator name this spelling uses, if a binding shadows it before use."""
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name):
            for names, check, label in ((export_names, is_export_name, 'export'),
                                        (dataclass_names, is_dataclass, 'dataclass')):
                if target.id in names and not check(decorator):
                    return label
        elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            for names, check, attr, label in ((module_names, is_export_name, 'export', 'export'),
                                              (dataclasses_modules, is_dataclass, 'dataclass', 'dataclass')):
                if target.attr == attr and target.value.id in names and not check(decorator):
                    return label
        return None

    dataclasses = {}
    for node in tree.body:
        if (not isinstance(node, ast.ClassDef) or node.bases
                or not node.decorator_list
                or not all(is_dataclass(d) for d in node.decorator_list)):
            continue
        fields = {}
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                annotation = statement.annotation
                fields[statement.target.id] = (annotation.id
                                               if isinstance(annotation, ast.Name)
                                               and annotation.id in SCALARS
                                               and not shadowed(annotation.id, statement.lineno)
                                               else None)
        dataclasses[node.name] = (node.lineno, fields)
    if future_annotations:
        # CPython's dataclass fields stay strings there, so @export refuses a dataclass parameter.
        dataclasses.clear()

    def allowed(annotation, result, line):
        if result and isinstance(annotation, ast.Constant) and annotation.value is None:
            return True
        if isinstance(annotation, ast.Name):
            if annotation.id in SCALARS:
                return not shadowed(annotation.id, line)
            if not result and annotation.id in dataclasses:
                defined, fields = dataclasses[annotation.id]
                # CPython evaluates the annotation at the def; a later class is a NameError there.
                rebound = any(defined < bound < line for bound, _, _ in bindings.get(annotation.id, ()))
                return (defined < line and not rebound
                        and all(kind in ('int', 'float', 'bool') for kind in fields.values()))
            return False
        if (isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name)
                and annotation.value.id == 'list' and not shadowed('list', line)
                and isinstance(annotation.slice, ast.Name)
                and annotation.slice.id in ('int', 'float')
                and not shadowed(annotation.slice.id, line)):
            return True
        return False

    targets, problems = [], []
    for node in ast.walk(tree):
        for decorator in getattr(node, 'decorator_list', ()):
            label = rebound_name(decorator)
            if label:
                problems.append('@%s %s: the name %s is rebound before the decorator, so this is '
                                'not the imported %s' % (
                                    label, getattr(node, 'name', '?'), label,
                                    'ail_ffi.export' if label == 'export' else 'dataclasses.dataclass'))
        if isinstance(node, ast.ClassDef):
            if any(is_export_name(decorator) for decorator in node.decorator_list):
                problems.append('@export applies to a top-level function')
            continue
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        export_marks = [decorator for decorator in node.decorator_list if is_export_name(decorator)]
        if not export_marks:
            continue
        if any(isinstance(decorator, ast.Call) and (decorator.args or decorator.keywords)
               for decorator in export_marks):
            problems.append('@export %s: the decorator takes no arguments' % node.name)
            continue
        marks = [decorator for decorator in node.decorator_list if is_export(decorator)]
        if any(is_export(decorator) and any(not is_export(lower) for lower in node.decorator_list[index + 1:])
               for index, decorator in enumerate(node.decorator_list)):
            problems.append('@export %s: no decorator below @export (CPython sees its result, '
                            'which may not be a function)' % node.name)
            continue
        args = node.args
        if (args.defaults or any(default is not None for default in args.kw_defaults)
                or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg):
            problems.append('@export %s: plain parameters without defaults only' % node.name)
            continue
        if node.returns is None:
            problems.append('@export %s: the result needs an annotation (-> None for no result)' % node.name)
            continue
        for argument in args.args:
            if argument.annotation is None or not allowed(argument.annotation, False, node.lineno):
                problems.append('@export %s: parameter %s needs one of int float bool str bytes '
                                'list[int] list[float] or a dataclass of int/float/bool'
                                % (node.name, argument.arg))
        if not allowed(node.returns, True, node.lineno):
            problems.append('@export %s: the result must be int float bool str bytes list[int] '
                            'list[float] or None' % node.name)
        targets.extend(marks)
    if problems:
        raise ExportError('\n'.join(problems))
    if not targets:
        return text
    lines = text.splitlines(keepends=True)
    for decorator in targets:
        for index in range(decorator.lineno - 1, decorator.end_lineno):
            ending = '\n' if lines[index].endswith('\n') else ''
            lines[index] = ' ' * (len(lines[index]) - len(ending)) + ending
    return ''.join(lines)


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
