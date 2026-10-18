"""Typed object contracts. Objects contain compiled code, never a source bundle."""
import ast
import builtins
import hashlib
import json
import keyword
import math
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile

from pipeline import PipelineError, compiler, ffi_link_args, link_flags
import native_diagnostics
from pyfront import Unsupported
import callable_types

FLAGS = ['-O2', '-fno-asynchronous-unwind-tables', '-ffp-contract=off']   # no FMA: see pyc.CFLAGS_TUNE
ABI_VERSION = 11
KINDS = {'int', 'float', 'str', 'bytes', 'bytearray', 'binaryfile', 'tcpsocket', 'exception'}
HANDLE_LIST_KINDS = {'handle_list:' + element for element in ('bytearray', 'binaryfile', 'tcpsocket', 'exception')}
PARAM_KINDS = KINDS | HANDLE_LIST_KINDS
FIELD_KINDS = KINDS | HANDLE_LIST_KINDS | {'list', 'flist', 'blist', 'slist', 'sdict', 'fdict', 'smap', 'bmap'}
RESERVED = set(dir(builtins)) | {'main', 'sys', 'jsdiv', 'jsnegzero', 'jscharat', 'wrapping_add', 'wrapping_sub', 'wrapping_mul', 'binaryfile', 'tcpsocket', 'exception'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def identity():
    tool = Path(shutil.which(compiler()) or compiler()).resolve(strict=True)
    def query(option):
        result = subprocess.run([str(tool), option], capture_output=True, timeout=20, check=True)
        return result.stdout.decode('utf8', errors='replace').strip()
    package = Path(__file__).resolve().parent
    return dict(platform=platform.system(), architecture=platform.machine(),
                compiler_sha256=digest(tool), compiler_version=query('--version'),
                target=query('-dumpmachine'), flags=FLAGS,
                implementation={name: digest(package / name) for name in
                                ('pyfunc.py', 'cruntime.py', 'float64_fusion.py', 'string_repeat_fusion.py', 'sortkeys.py', 'parallel.py', 'pyc.py', 'module_object.py', 'c_object.py',
                                 'pyfront.py', 'pipeline.py', 'native_diagnostics.py', 'c_api_bridge.py', 'callable_types.py',
                                 'borrowed_callback.py')})


def contract_symbol(contract):
    return 'ail_object_abi_' + hashlib.sha256(canonical(contract)).hexdigest()


def _valid_name(name):
    return (isinstance(name, str) and bool(re.fullmatch(r'[A-Za-z_]\w*', name))
            and name.isidentifier() and not keyword.iskeyword(name) and name not in RESERVED)


def _valid_constant(name, constant):
    if (not _valid_name(name)
            or not isinstance(constant, dict) or set(constant) != {'type', 'value'}):
        raise ValueError('invalid constant name or fields')
    kind, value = constant['type'], constant['value']
    if (kind == 'int' and type(value) is int and -(1 << 63) <= value < 1 << 63
            or kind == 'float' and type(value) is float and math.isfinite(value)
            or kind == 'str' and type(value) is str
            or kind == 'bytes' and type(value) is str and re.fullmatch(r'(?:[0-9a-f]{2})*', value)):
        if kind == 'str':
            value.encode('utf8')  # Match the existing literal rule: no lone surrogates.
        return
    raise ValueError('constant requires a finite float, signed int64, Unicode str, or canonical bytes hex of its declared type')


def _constant_source(constants):
    declarations = [ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())],
                                value=ast.Constant(value=bytes.fromhex(constant['value'])
                                                   if constant['type'] == 'bytes' else constant['value']))
                    for name, constant in constants.items()]
    return ast.unparse(ast.fix_missing_locations(ast.Module(body=declarations, type_ignores=[]))) + '\n'


def _valid_method_kind(kind, *, result=False):
    return (isinstance(kind, str)
            and (kind in KINDS | HANDLE_LIST_KINDS | {'flist', 'slist', 'sdict', 'fdict', 'smap', 'bmap', 'blist', 'list' if result else 'array'} | ({'noret'} if result else set())
                 or kind.startswith(('struct:', 'struct_list:')) and _valid_name(kind.partition(':')[2])
                 or callable_types.valid(kind)))


def _valid_struct(name, spec):
    if (not _valid_name(name) or not isinstance(spec, dict) or set(spec) not in ({'fields'}, {'fields', 'methods'})
            or not isinstance(spec['fields'], list) or not spec['fields']
            or any(not isinstance(field, list) or len(field) != 2
                   or not isinstance(field[0], str) or not re.fullmatch(r'[A-Za-z_]\w*', field[0])
                   or not field[0].isidentifier() or keyword.iskeyword(field[0]) or field[0] == 'self'
                   or not isinstance(field[1], str)
                   or not (field[1] in FIELD_KINDS or field[1].startswith(('struct:', 'struct_list:'))
                           and _valid_name(field[1].partition(':')[2])
                           or callable_types.valid(field[1])) for field in spec['fields'])
            or len({field[0] for field in spec['fields']}) != len(spec['fields'])):
        raise ValueError('invalid struct name, fields, or supported scalar/container types')
    methods = spec.get('methods', {})
    if (not isinstance(methods, dict) or 'methods' in spec and not methods
            or any(not isinstance(method, str) or not method.isidentifier()
                   or not re.fullmatch(r'[A-Za-z_]\w*', method) or keyword.iskeyword(method)
                   or method.startswith('__') and method.endswith('__')
                   or method in {field for field, _ in spec['fields']}
                   or not isinstance(signature, dict) or set(signature) != {'params', 'result', 'function'}
                   or signature['function'] != f'__ail_method_{name}_{method}'
                   or not isinstance(signature['params'], list)
                   or any(not isinstance(param, list) or len(param) != 2
                          or not isinstance(param[0], str) or not param[0].isidentifier()
                          or keyword.iskeyword(param[0]) or not re.fullmatch(r'[A-Za-z_]\w*', param[0])
                          or param[0] == 'self' or not _valid_method_kind(param[1])
                          for param in signature['params'])
                   or len({param[0] for param in signature['params']}) != len(signature['params'])
                   or not _valid_method_kind(signature['result'], result=True)
                   for method, signature in methods.items())):
        raise ValueError('invalid struct method name or descriptor')


def _method_kind(annotation, structs, *, integer_lists=False, result=False):
    from pyfunc import _annotation_kind, FLIST, SLIST, SDICT, FDICT, SMAP, BMAP, LIST
    callback = _callable_annotation(annotation, structs)
    if callback is not None:
        return callback
    if (result and isinstance(annotation, ast.Name)
            and annotation.id.startswith('__ail_checked_') and annotation.id.endswith('__')):
        annotation = ast.Name(id=annotation.id[len('__ail_checked_'):-2], ctx=ast.Load())
    list_kind = _struct_list_annotation(annotation, structs)
    if list_kind:
        return list_kind
    if isinstance(annotation, ast.Name) and annotation.id in structs and annotation.id not in KINDS:
        return 'struct:' + annotation.id
    if integer_lists and _annotation_kind(annotation) == FLIST:
        return FLIST
    if integer_lists and _annotation_kind(annotation) == SLIST:
        return SLIST
    if integer_lists and _annotation_kind(annotation) == SDICT:
        return SDICT
    if integer_lists and _annotation_kind(annotation) == FDICT:
        return FDICT
    if integer_lists and _annotation_kind(annotation) == SMAP:
        return SMAP
    if integer_lists and _annotation_kind(annotation) == BMAP:
        return BMAP
    if integer_lists and _annotation_kind(annotation) == LIST:
        return 'list' if result else 'array'
    if integer_lists and _annotation_kind(annotation) == 'blist':
        return 'blist'
    if isinstance(annotation, ast.Name):
        if result and annotation.id == 'void':
            return 'noret'
        if annotation.id in KINDS:
            return annotation.id
        if integer_lists and result and annotation.id in (FLIST, SLIST, SDICT, FDICT, SMAP, BMAP):
            return annotation.id
        if integer_lists and annotation.id == 'list':
            return 'list' if result else 'array'
    raise Unsupported('object methods require explicit supported parameter and result annotations')


def _struct_spec(node, known_structs=(), *, integer_lists=False):
    from pyfunc import _annotation_kind
    if (node.bases or node.keywords or node.decorator_list or not node.body
            or not isinstance(node.body[0], ast.FunctionDef) or node.body[0].name != '__init__'):
        raise Unsupported('object structs require a plain field-only constructor')
    names = {'__init__'}
    for method in node.body[1:]:
        if (not isinstance(method, ast.FunctionDef) or method.name in names
                or keyword.iskeyword(method.name) or method.decorator_list
                or not method.args.args or method.args.args[0].arg != 'self'
                or method.args.args[0].annotation is not None
                or method.args.defaults or method.args.kw_defaults or method.args.posonlyargs
                or method.args.kwonlyargs or method.args.vararg or method.args.kwarg
                or len({arg.arg for arg in method.args.args}) != len(method.args.args)
                or any(arg.annotation is None for arg in method.args.args[1:])):
            raise Unsupported('object struct methods require distinct names and plain typed parameters after self')
        names.add(method.name)
    init = node.body[0]
    args = init.args
    if (init.decorator_list or args.defaults or args.kw_defaults or args.posonlyargs or args.kwonlyargs
            or args.vararg or args.kwarg or not args.args or args.args[0].arg != 'self'
            or len(args.args) != len(init.body) + 1):
        raise Unsupported('object structs require one constructor parameter per field')
    fields = []
    for arg, stmt in zip(args.args[1:], init.body):
        kind = (_callable_annotation(arg.annotation, known_structs)
                or _struct_list_annotation(arg.annotation, known_structs)
                or ('struct:' + arg.annotation.id if isinstance(arg.annotation, ast.Name)
                    and arg.annotation.id in known_structs else None)
                or (arg.annotation.id if isinstance(arg.annotation, ast.Name) and arg.annotation.id in KINDS
                    else _annotation_kind(arg.annotation) if _annotation_kind(arg.annotation) in FIELD_KINDS else None))
        if (kind not in FIELD_KINDS and not callable_types.valid(kind)
                and not (isinstance(kind, str) and kind.startswith(('struct:', 'struct_list:')))
                or not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1
                or not isinstance(stmt.targets[0], ast.Attribute)
                or not isinstance(stmt.targets[0].value, ast.Name) or stmt.targets[0].value.id != 'self'
                or stmt.targets[0].attr != arg.arg or not isinstance(stmt.value, ast.Name)
                or stmt.value.id != arg.arg):
            raise Unsupported('object structs require ordered scalar or supported list parameters assigned to same-named fields')
        fields.append([arg.arg, kind])
    if (names - {'__init__'}).intersection(field for field, _ in fields):
        raise Unsupported('object struct methods cannot have the same name as a field')
    methods = {method.name: dict(
        params=[[arg.arg, _method_kind(arg.annotation, known_structs, integer_lists=integer_lists)]
                for arg in method.args.args[1:]],
        result=_method_kind(method.returns, known_structs, integer_lists=integer_lists, result=True),
        function=f'__ail_method_{node.name}_{method.name}') for method in node.body[1:]}
    if any(methods[method.name]['result'] == 'noret'
           and any(isinstance(stmt, ast.Return) and stmt.value is not None for stmt in ast.walk(method))
           for method in node.body[1:]):
        raise Unsupported('void object methods cannot return a value')
    spec = dict(fields=fields, **({'methods': methods} if methods else {}))
    try:
        _valid_struct(node.name, spec)
    except ValueError as error:
        raise Unsupported(str(error)) from error
    return spec


def _struct_source(structs):
    _validate_struct_graph(structs)
    declarations = []
    for name, spec in structs.items():
        _valid_struct(name, spec)
        params = ', '.join(f'{field}: {_kind_annotation(kind)}' for field, kind in spec['fields'])
        fields = '\n'.join(f'        self.{field} = {field}' for field, _ in spec['fields'])
        methods = []
        for method, signature in spec.get('methods', {}).items():
            method_params = ', '.join(f'{param}: {_kind_annotation(kind)}' for param, kind in signature['params'])
            arguments = ', '.join(['self', *(param for param, _ in signature['params'])])
            action = '' if signature['result'] == 'noret' else 'return '
            methods.append(f'    def {method}(self{", " + method_params if method_params else ""})'
                           f' -> {_kind_annotation(signature["result"])}:\n'
                           f'        {action}{signature["function"]}({arguments})\n')
        declarations.append(f'class {name}:\n    def __init__(self, {params}):\n{fields}\n' + ''.join(methods))
    return '\n'.join(declarations)


def _validate_struct_graph(structs):
    for name, spec in structs.items():
        _valid_struct(name, spec)
        for _, kind in spec['fields']:
            if callable_types.valid(kind):
                unknown = callable_types.struct_names(kind) - structs.keys()
                if unknown:
                    raise ValueError('unknown struct callable field type: ' + ', '.join(sorted(unknown)))
        for method in spec.get('methods', {}).values():
            for kind in [method['result'], *(kind for _, kind in method['params'])]:
                names = (callable_types.struct_names(kind) if callable_types.valid(kind)
                         else {kind.partition(':')[2]} if kind.startswith(('struct:', 'struct_list:')) else set())
                if names - structs.keys():
                    raise ValueError('unknown struct method signature type: ' + ', '.join(sorted(names - structs.keys())))
    visiting, done = set(), set()
    for root in structs:
        stack = [(root, False)]
        while stack:
            name, exiting = stack.pop()
            if exiting:
                visiting.remove(name)
                done.add(name)
                continue
            if name not in structs:
                raise ValueError('unknown struct field type: ' + name)
            if name in visiting:
                raise ValueError('cyclic struct fields are unsupported')
            if name in done:
                continue
            visiting.add(name)
            children = [kind.partition(':')[2] for _, kind in structs[name]['fields']
                        if kind.startswith(('struct:', 'struct_list:'))]
            stack.append((name, True))
            stack.extend((child, False) for child in reversed(children))


def _kind_annotation(kind):
    if kind in HANDLE_LIST_KINDS:
        return 'list[' + kind.partition(':')[2] + ']'
    if callable_types.valid(kind):
        return callable_types.annotation(kind)
    if kind.startswith('struct_list:'):
        return 'list[' + kind[len('struct_list:'):] + ']'
    if kind.startswith('struct:'):
        return kind[len('struct:'):]
    return {'array': 'list', 'list': 'list[int]', 'flist': 'list[float]', 'slist': 'list[str]', 'sdict': 'dict[str, int]', 'fdict': 'dict[str, float]', 'smap': 'dict[str, str]', 'bmap': 'dict[str, bytes]', 'blist': 'list[bytes]', 'noret': 'void'}.get(kind, kind)


def native_kind(kind):
    if kind in HANDLE_LIST_KINDS:
        return ('hlist', kind.partition(':')[2])
    if kind.startswith('struct_list:'):
        return ('olist', kind[len('struct_list:'):])
    return ('obj', kind[len('struct:'):]) if kind.startswith('struct:') else kind


def _struct_list_annotation(annotation, structs):
    if (isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name)
            and annotation.value.id in ('list', '__ail_checked_list')
            and isinstance(annotation.slice, ast.Name)
            and annotation.slice.id in ('bytearray', 'binaryfile', 'tcpsocket', 'exception')
            and annotation.slice.id not in structs):
        return 'handle_list:' + annotation.slice.id
    if (isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name)
            and annotation.value.id in ('list', '__ail_checked_list')
            and isinstance(annotation.slice, ast.Name) and annotation.slice.id in structs):
        return 'struct_list:' + annotation.slice.id
    return None


def _signature_kinds(signature):
    return ([(name, native_kind(kind)) for name, kind in signature['params']], native_kind(signature['result']))


def _callable_annotation(annotation, structs=()):
    try:
        return callable_types.parse(annotation, structs)
    except ValueError as error:
        raise Unsupported(str(error)) from error


def _valid_export_kind(kind, kinds, *, result=False):
    return (isinstance(kind, str)
            and (kind in KINDS | HANDLE_LIST_KINDS | kinds | ({'list', 'noret'} if result else {'array'})
                 | {'flist', 'slist', 'sdict', 'fdict', 'smap', 'bmap', 'blist'}
                 or callable_types.valid(kind)
                 and all('struct:' + name in kinds for name in callable_types.struct_names(kind))))


def typed_module(source, *, integer_lists=False, structs=None, imported_structs=None):
    from pyfunc import _module_const_scalar, _annotation_kind, _olist_sort_spec, FLIST, SLIST, SDICT, FDICT, SMAP, BMAP, LIST
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    imported_structs = imported_structs or {}
    constants, declared = {}, set()
    known_struct_names = set(imported_structs) | {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    if not tree.body:
        raise Unsupported('object module requires typed functions or scalar constants')
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            name = node.name
        elif isinstance(node, ast.ClassDef) and structs is not None:
            name = node.name
            structs[name] = _struct_spec(node, known_struct_names, integer_lists=integer_lists)
        elif (isinstance(node, ast.Assign) and len(node.targets) == 1
              and isinstance(node.targets[0], ast.Name)):
            name = node.targets[0].id
            scalar = _module_const_scalar(node.value)
            if scalar is None:
                raise Unsupported('object constants require int/float/str/bytes literals')
            constant = dict(type=scalar[0], value=scalar[1].hex() if scalar[0] == 'bytes' else scalar[1])
            try:
                _valid_constant(name, constant)
            except ValueError as error:
                raise Unsupported(str(error)) from error
            constants[name] = constant
        else:
            raise Unsupported('object modules require only typed functions, numeric structs, and scalar literal constants')
        if name in declared:
            raise Unsupported('duplicate object export: ' + name)
        declared.add(name)
    for owner, spec in (structs or {}).items():
        for method, signature in spec.get('methods', {}).items():
            name = signature['function']
            if name in declared:
                raise Unsupported('generated object method adapter collides with a declaration: ' + name)
            declared.add(name)
            params = ', '.join(f'{param}: {_kind_annotation(kind)}' for param, kind in signature['params'])
            arguments = ', '.join(param for param, _ in signature['params'])
            action = '' if signature['result'] == 'noret' else 'return '
            adapter = ast.parse(f'def {name}(self: {owner}{", " + params if params else ""})'
                                f' -> {_kind_annotation(signature["result"])}:\n'
                                f'    {action}self.{method}({arguments})\n').body[0]
            functions.append(adapter)
            tree.body.append(adapter)
    exports = {}
    known_structs = {**imported_structs, **(structs or {})}
    try:
        _validate_struct_graph(known_structs)
    except ValueError as error:
        raise Unsupported(str(error)) from error
    prefix = 'ail_object_' + hashlib.sha256(source.encode()).hexdigest()[:24] + '_'
    def returns(statements):
        def loop_exit(body):
            pending = list(body)
            while pending:
                node = pending.pop()
                if isinstance(node, (ast.Break, ast.Continue)):
                    return True
                if isinstance(node, (ast.For, ast.While)):
                    pending.extend(node.orelse)
                elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    pending.extend(ast.iter_child_nodes(node))
            return False

        return any(isinstance(node, ast.Return) and node.value is not None
                   or isinstance(node, ast.Raise)
                   or isinstance(node, ast.If) and node.orelse
                   and returns(node.body) and returns(node.orelse)
                   or isinstance(node, ast.Try)
                   and (returns(node.finalbody)
                        or not loop_exit(node.finalbody)
                        and all(returns(handler.body) for handler in node.handlers)
                        and (returns(node.body) or node.orelse and returns(node.orelse)))
                   for node in statements)
    for fn in functions:
        if fn.name in RESERVED:
            raise Unsupported('object exports cannot use a reserved builtin name: ' + fn.name)
        args = fn.args
        if (fn.name in exports or fn.name == 'main' or fn.decorator_list or args.defaults
                or args.kw_defaults or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg):
            raise Unsupported('object functions require distinct non-main names and plain parameters without defaults')
        params = []
        for arg in args.args:
            callback = _callable_annotation(arg.annotation, known_structs)
            if callback is not None:
                params.append([arg.arg, callback])
                continue
            list_kind = _struct_list_annotation(arg.annotation, known_structs)
            if list_kind:
                params.append([arg.arg, list_kind])
                continue
            if isinstance(arg.annotation, ast.Name) and arg.annotation.id in known_structs:
                params.append([arg.arg, 'struct:' + arg.annotation.id])
                continue
            if integer_lists and _annotation_kind(arg.annotation) == FLIST:
                params.append([arg.arg, FLIST])
                continue
            if integer_lists and _annotation_kind(arg.annotation) == SLIST:
                params.append([arg.arg, SLIST])
                continue
            if integer_lists and _annotation_kind(arg.annotation) == SDICT:
                params.append([arg.arg, SDICT])
                continue
            if integer_lists and _annotation_kind(arg.annotation) == FDICT:
                params.append([arg.arg, FDICT])
                continue
            if integer_lists and _annotation_kind(arg.annotation) == SMAP:
                params.append([arg.arg, SMAP])
                continue
            if integer_lists and _annotation_kind(arg.annotation) == BMAP:
                params.append([arg.arg, BMAP])
                continue
            if integer_lists and _annotation_kind(arg.annotation) == LIST:
                params.append([arg.arg, 'array'])
                continue
            if integer_lists and _annotation_kind(arg.annotation) == 'blist':
                params.append([arg.arg, 'blist'])
                continue
            kinds = PARAM_KINDS | ({'list'} if integer_lists else set())
            if not isinstance(arg.annotation, ast.Name) or arg.annotation.id not in kinds:
                raise Unsupported('object parameters require explicit int, float, str, or bytes annotations'
                                  + (' or a flat list of int64, float, str, or bytes' if integer_lists else ''))
            params.append([arg.arg, 'array' if arg.annotation.id == 'list' else arg.annotation.id])
        callback_result = _callable_annotation(fn.returns, known_structs)
        result = callback_result or (fn.returns.id if isinstance(fn.returns, ast.Name) else '')
        list_result = _struct_list_annotation(fn.returns, known_structs)
        if list_result:
            result = list_result
        if callback_result is None and integer_lists and _annotation_kind(fn.returns) == FLIST:
            result = FLIST
        if callback_result is None and integer_lists and _annotation_kind(fn.returns) == SLIST:
            result = SLIST
        if callback_result is None and integer_lists and _annotation_kind(fn.returns) == SDICT:
            result = SDICT
        if callback_result is None and integer_lists and _annotation_kind(fn.returns) == FDICT:
            result = FDICT
        if callback_result is None and integer_lists and _annotation_kind(fn.returns) == SMAP:
            result = SMAP
        if callback_result is None and integer_lists and _annotation_kind(fn.returns) == BMAP:
            result = BMAP
        if callback_result is None and integer_lists and _annotation_kind(fn.returns) == LIST:
            result = 'list'
        if callback_result is None and integer_lists and _annotation_kind(fn.returns) == 'blist':
            result = 'blist'
        if result.startswith('__ail_checked_') and result.endswith('__'):
            result = result[len('__ail_checked_'):-2]
        if callback_result is None and result not in KINDS | HANDLE_LIST_KINDS | {'void'} | known_structs.keys() | {'struct_list:' + name for name in known_structs} | ({'list', 'flist', 'slist', 'sdict', 'fdict', 'smap', 'bmap', 'blist'} if integer_lists else set()):
            raise Unsupported('object results require explicit int, float, str, bytes, or void annotations'
                              + (' or a flat list of int64, float, str, or bytes' if integer_lists else ''))
        # These lambdas are pure compile-time field specifications, never closures or exports.
        sort_keys = {kw.value for node in ast.walk(fn)
                     if isinstance(node, ast.Call) and (
                         isinstance(node.func, ast.Attribute) and node.func.attr == 'sort'
                         and isinstance(node.func.value, ast.Name)
                         or isinstance(node.func, ast.Name) and node.func.id == 'sorted')
                     for kw in node.keywords if kw.arg == 'key' and isinstance(kw.value, ast.Lambda)}
        for key in sort_keys:
            _olist_sort_spec(key)
        if any(isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom,
                                 ast.Global, ast.Nonlocal)) or isinstance(node, ast.Lambda) and node not in sort_keys
               for statement in fn.body for node in ast.walk(statement)):
            raise Unsupported('object functions do not support nested definitions, imports, or globals')
        if result == 'void':
            if any(isinstance(node, ast.Return) and node.value is not None for node in ast.walk(fn)):
                raise Unsupported('void object functions cannot return a value')
        else:
            if any(isinstance(node, ast.Return) and node.value is None for node in ast.walk(fn)):
                raise Unsupported('object functions must return a typed value')
            if not returns(fn.body):
                raise Unsupported('object results need a value on every path')
        exports[fn.name] = dict(params=params, result='struct:' + result if result in known_structs
                              else 'noret' if result == 'void' else result, symbol=prefix + fn.name,
                                owned_str=result == 'str', owned_bytes=result == 'bytes')
        fn.returns = (fn.returns if callback_result is not None else ast.Subscript(value=ast.Name(id='__ail_checked_list', ctx=ast.Load()),
                                    slice=ast.Name(id='bytes' if result == 'blist' else result.partition(':')[2], ctx=ast.Load()), ctx=ast.Load())
                      if list_result or result == 'blist' else ast.Name(id='__ail_checked_' + result + '__', ctx=ast.Load()))
    # Rename only real module function definitions/references; callers see metadata names.
    names = {name: value['symbol'] for name, value in exports.items()}
    method_functions = [method for node in tree.body if isinstance(node, ast.ClassDef)
                        for method in node.body[1:]]
    for fn in [*functions, *method_functions]:
        shadowed = {arg.arg for arg in fn.args.args} | {
            node.id for node in ast.walk(fn)
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))}
        if shadowed & declared:
            raise Unsupported('object function/constant names cannot be rebound or shadowed')
    class Rename(ast.NodeTransformer):
        def visit_ClassDef(self, node):
            for method in node.body[1:]:
                method.body = [self.visit(stmt) for stmt in method.body]
            return node
        def visit_FunctionDef(self, node):
            node.name = names[node.name]
            return self.generic_visit(node)
        def visit_Lambda(self, node):
            # Only validated field-key lambdas survived; their names are locally bound.
            return node
        def visit_Name(self, node):
            if node.id in names:
                node.id = names[node.id]
            return node
    return ast.unparse(ast.fix_missing_locations(Rename().visit(tree))), exports, constants


def _check_external_names(source, exports):
    tree = ast.parse(source)
    shadows = {node.id for node in ast.walk(tree)
               if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))}
    shadows.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
    shadows.update(node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef)))
    if shadows & exports.keys():
        raise Unsupported('external object functions/constants cannot be rebound or shadowed')


def _binding_references(bindings, prefix):
    return ''.join('extern const unsigned char %s;\n'
                   'const void * const %s_%d = &%s;\n' % (symbol, prefix, index, symbol)
                   for index, symbol in enumerate(bindings))


def compile_object(source, output, paths=(), *, c_api_namespace=None):
    output = Path(output).resolve()
    metadata_path = Path(str(output) + '.json')
    if output.exists() or metadata_path.exists():
        raise Unsupported('object output or its metadata already exists')
    dependencies = load_objects(paths, require_dependencies=False, c_api_namespace=c_api_namespace) if paths else {}
    structs = {}
    renamed, exports, constants = typed_module(source, integer_lists=True, structs=structs,
                                               imported_structs=dependencies.get('structs', {}))
    if c_api_namespace is not None and (structs or dependencies.get('structs')):
        raise Unsupported('numeric struct objects use the AIL ABI; C API struct exports are unsupported')
    if c_api_namespace is not None:
        from c_api_bridge import namespace_module, validate_source
        validate_source(source)
        renamed = namespace_module(renamed, exports, c_api_namespace)
    _check_external_names(source, {**dependencies.get('exports', {}), **dependencies.get('constants', {}),
                                   **dependencies.get('structs', {})})
    before = identity()
    from pyfunc import to_c
    info = {'_want_units': True, '_checked_arrays': True}
    body = to_c(_constant_source(dependencies.get('constants', {})) + renamed,
                strict=True, info=info, library=True, external=dependencies)
    if any(info['function_signatures'][signature['symbol']]
           != _signature_kinds(signature)
           for signature in exports.values()):
        raise Unsupported('public object annotation disagrees with inferred signature')
    if (any(info.get('function_array_shapes', {}).values())
            or any(info['function_signatures'].get(name, ((), None))[1] != 'blist'
                   for name in info.get('nonflat_list_returns', ()))):
        raise Unsupported('object list contracts require supported flat elements, not rows, grids, or untyped handles')
    contract = dict(version=ABI_VERSION, exports=exports, constants=constants, structs=structs,
                    runtime_parts=info['runtime_parts'],
                    readonly_scalar_helpers=sorted(name for name, spec in exports.items()
                                                   if spec['symbol'] in info.get('readonly_scalar_helpers', ())),
                    non_escaping_string_helpers=sorted(name for name, spec in exports.items()
                                                       if spec['symbol'] in info.get('non_escaping_string_helpers', ())),
                    dependencies=dependencies.get('dependencies', []),
                    libm=info.get('libm', False), io=info.get('io', False), identity=before)
    if c_api_namespace is not None:
        contract['c_api_namespace'] = c_api_namespace
    symbol = contract_symbol(contract)
    code = ('#define AIL_LINK_STATE(type, name, init) extern type name\n'
            '#define AIL_LINK_EXPORT static\n' + body
            + _binding_references(dependencies.get('bindings', []), symbol + '_dependency')
            + '\nconst unsigned char ' + symbol + ' = 0;\n')
    if c_api_namespace is not None:
        from c_api_bridge import object_prefix
        code = object_prefix(code, c_api_namespace)
    with tempfile.TemporaryDirectory(prefix='ail-object-') as directory:
        c_path = Path(directory) / 'module.c'
        temporary_object = Path(directory) / 'module.o'
        c_path.write_text(code, encoding='utf8')
        native_diagnostics.generated(c_path, info.get('c_source_regions', info.get('c_units', (None, []))[1]))
        result = native_diagnostics.run([compiler(), *FLAGS, '-c', str(c_path), '-o', str(temporary_object)],
                                capture_output=True, timeout=120, phase='compile')
        if result.returncode:
            raise PipelineError('module C compile failed: ' + result.stderr.decode(errors='replace')[-2000:])
        if identity() != before:
            raise Unsupported('compiler/runtime identity changed during object build')
        if paths and load_objects(paths, require_dependencies=False, c_api_namespace=c_api_namespace) != dependencies:
            raise Unsupported('dependency objects changed during object build')
        envelope = dict(contract=contract, object_sha256=digest(temporary_object))
        created = False
        try:
            with output.open('xb') as destination:
                created = True
                destination.write(temporary_object.read_bytes())
            with metadata_path.open('x', encoding='utf8') as destination:
                destination.write(json.dumps(envelope, indent=2) + '\n')
        except Exception:
            if created:
                output.unlink()
            raise
    return output


def load_objects(paths, *, require_dependencies=True, c_api_namespace=None):
    import cruntime
    if c_api_namespace is not None:
        from c_api_bridge import validate_namespace
        validate_namespace(c_api_namespace)
    loaded = []
    for path in paths:
        try:
            path = Path(path).resolve(strict=True)
            envelope = json.loads(Path(str(path) + '.json').read_text(encoding='utf8'))
            loaded.append((path, envelope))
        except (ValueError, OSError) as error:
            raise Unsupported('invalid object metadata: ' + str(error)) from error
    current = identity()
    exports, constants, parts, bindings, objects = {}, {}, set(), [], []
    structs, struct_owners, envelopes = {}, {}, []
    readonly_scalar_helpers = set()
    non_escaping_string_helpers = set()
    supplied, required, object_hashes = {}, [], {}
    libm = io = False
    for path, envelope in loaded:
        try:
            contract = envelope['contract']
            if type(contract['version']) is not int or contract['version'] != ABI_VERSION or contract['identity'] != current:
                raise ValueError('runtime, compiler, target, or ABI identity mismatch')
            if digest(path) != envelope['object_sha256']:
                raise ValueError('object hash mismatch')
            if not isinstance(contract['structs'], dict):
                raise ValueError('invalid object structs')
            for name, spec in contract['structs'].items():
                _valid_struct(name, spec)
                if name in structs:
                    raise ValueError('duplicate numeric struct provider')
                structs[name] = spec
                struct_owners[name] = contract_symbol(contract)
            if c_api_namespace is not None and contract['structs']:
                raise ValueError('C API struct object dependencies are unsupported')
            envelopes.append((path, envelope))
        except (KeyError, TypeError, ValueError, OSError) as error:
            raise Unsupported('invalid object metadata: ' + str(error)) from error
    kinds = {prefix + name for name in structs for prefix in ('struct:', 'struct_list:')}
    try:
        _validate_struct_graph(structs)
    except ValueError as error:
        raise Unsupported('invalid object metadata: ' + str(error)) from error
    for path, envelope in envelopes:
        try:
            contract = envelope['contract']
            fields = {'version', 'exports', 'constants', 'structs', 'runtime_parts', 'libm', 'io',
                      'identity', 'dependencies', 'readonly_scalar_helpers'}
            if c_api_namespace is not None:
                fields.add('c_api_namespace')
            if set(contract) - {'non_escaping_string_helpers'} != fields:
                raise ValueError('invalid object contract fields')
            if contract.get('c_api_namespace') != c_api_namespace:
                raise ValueError('C API dependency namespace mismatch')
            if (not isinstance(contract['exports'], dict) or not isinstance(contract['constants'], dict)
                    or not (contract['exports'] or contract['constants'] or contract['structs'])
                    or type(contract['libm']) is not bool or type(contract['io']) is not bool
                    or not isinstance(contract['runtime_parts'], list)
                    or any(not isinstance(part, str) or part not in cruntime.SOURCE
                           for part in contract['runtime_parts'])):
                raise ValueError('invalid object requirements')
            dependencies = contract['dependencies']
            if (not isinstance(dependencies, list)
                    or any(not isinstance(dependency, dict)
                           or set(dependency) != {'abi', 'object_sha256'}
                           or not isinstance(dependency['abi'], str)
                           or not re.fullmatch(r'ail_object_abi_[0-9a-f]{64}', dependency['abi'])
                           or not isinstance(dependency['object_sha256'], str)
                           or not re.fullmatch(r'[0-9a-f]{64}', dependency['object_sha256'])
                           for dependency in dependencies)
                    or len({dependency['abi'] for dependency in dependencies}) != len(dependencies)):
                raise ValueError('invalid dependency contracts')
            required.extend(dependencies)
            dependency_abis = {dependency['abi'] for dependency in dependencies}
            for spec in contract['structs'].values():
                for _, kind in spec['fields']:
                    targets = (callable_types.struct_names(kind) if callable_types.valid(kind)
                               else {kind.partition(':')[2]} if kind.startswith(('struct:', 'struct_list:')) else set())
                    for target in targets:
                        if target not in contract['structs'] and struct_owners[target] not in dependency_abis:
                            raise ValueError('struct field is not bound to its provider dependency')
            for name, signature in contract['exports'].items():
                if (not _valid_name(name)
                        or name in exports or name in constants or name in structs
                        or not isinstance(signature, dict)
                        or set(signature) != {'params', 'result', 'symbol', 'owned_str', 'owned_bytes'}
                        or not _valid_export_kind(signature['result'], kinds, result=True)
                        or signature['owned_str'] is not (signature['result'] == 'str')
                        or signature['owned_bytes'] is not (signature['result'] == 'bytes')
                        or not isinstance(signature['symbol'], str)
                        or not re.fullmatch((re.escape(c_api_namespace + '_ail_dependency_') if c_api_namespace is not None else '')
                                            + r'ail_object_[0-9a-f]{24}_[A-Za-z_]\w*', signature['symbol'])
                        or not isinstance(signature['params'], list)
                        or any(not isinstance(param, list) or len(param) != 2
                               or not isinstance(param[0], str) or not param[0].isidentifier()
                               or keyword.iskeyword(param[0]) or not re.fullmatch(r'[A-Za-z_]\w*', param[0])
                               or not _valid_export_kind(param[1], kinds) for param in signature['params'])
                        or len({param[0] for param in signature['params']}) != len(signature['params'])):
                    raise ValueError('invalid or duplicate exported signature')
                referenced = {kind.partition(':')[2] for kind in
                              [signature['result'], *(kind for _, kind in signature['params'])]
                              if kind.startswith(('struct:', 'struct_list:'))}
                referenced.update(name for kind in [signature['result'], *(kind for _, kind in signature['params'])]
                                  if callable_types.valid(kind) for name in callable_types.struct_names(kind))
                dependency_abis = {dependency['abi'] for dependency in dependencies}
                if any(name not in contract['structs'] and struct_owners[name] not in dependency_abis
                       for name in referenced):
                    raise ValueError('struct signature is not bound to its provider dependency')
                exports[name] = signature
            for owner, spec in contract['structs'].items():
                for method, descriptor in spec.get('methods', {}).items():
                    signature = contract['exports'].get(descriptor['function'])
                    if (signature is None
                            or signature['params'] != [['self', 'struct:' + owner], *descriptor['params']]
                            or signature['result'] != descriptor['result']
                            or not signature['symbol'].endswith('_' + descriptor['function'])):
                        raise ValueError('struct method adapter does not match its provider export')
            helpers = contract['readonly_scalar_helpers']
            if (not isinstance(helpers, list) or any(not isinstance(name, str) for name in helpers)
                    or len(set(helpers)) != len(helpers)
                    or any(name not in contract['exports'] or exports[name]['result'] not in {'int', 'float'}
                           or any(kind not in {'int', 'float', 'str'} for _, kind in exports[name]['params'])
                           for name in helpers)):
                raise ValueError('invalid readonly scalar helper summary')
            readonly_scalar_helpers.update(helpers)
            helpers = contract.get('non_escaping_string_helpers', [])
            if (not isinstance(helpers, list) or any(not isinstance(name, str) for name in helpers)
                    or len(set(helpers)) != len(helpers)
                    or any(name not in contract['exports'] or exports[name]['result'] not in {'int', 'float', 'list', 'flist'}
                           or not any(kind == 'str' for _, kind in exports[name]['params'])
                           for name in helpers)):
                raise ValueError('invalid non-escaping string helper summary')
            non_escaping_string_helpers.update(helpers)
            for name, constant in contract['constants'].items():
                _valid_constant(name, constant)
                if name in exports or name in constants or name in structs:
                    raise ValueError('duplicate function/constant export')
                constants[name] = constant
            parts.update(contract['runtime_parts'])
            binding = contract_symbol(contract)
            bindings.append(binding)
            supplied[binding] = envelope['object_sha256']
            object_hashes[str(path)] = envelope['object_sha256']
            libm |= contract['libm']
            io |= contract['io']
            objects.append(str(path))
        except (KeyError, TypeError, ValueError, OSError) as error:
            raise Unsupported('invalid object metadata: ' + str(error)) from error
    for dependency in required:
        if dependency['abi'] not in supplied:
            if require_dependencies:
                raise Unsupported('missing dependency object for ABI ' + dependency['abi'])
        elif supplied[dependency['abi']] != dependency['object_sha256']:
            raise Unsupported('dependency object hash does not match required contract')
    return dict(exports=exports, constants=constants, structs=structs,
                runtime_parts=sorted(parts), bindings=bindings,
                readonly_scalar_helpers=sorted(readonly_scalar_helpers),
                non_escaping_string_helpers=sorted(non_escaping_string_helpers),
                objects=objects, object_hashes=object_hashes, libm=libm, io=io,
                dependencies=[dict(abi=binding, object_sha256=object_hash)
                              for binding, object_hash in supplied.items()])


def link_objects(source, output, paths, *, unit_map=None):
    from pyc import _io_main_for, _main_for, _finalize_output, to_c, build_link_units
    from pyfunc import NORET
    metadata = load_objects(paths)
    _check_external_names(source, {**metadata['exports'], **metadata['constants'], **metadata['structs']})
    source = _constant_source(metadata['constants']) + source
    with tempfile.TemporaryDirectory(prefix='ail-object-entry-') as directory:
        staged_objects = []
        for index, original in enumerate(metadata['objects']):
            staged = Path(directory) / ('module%d.o' % index)
            staged.write_bytes(Path(original).read_bytes())
            if digest(staged) != metadata['object_hashes'][original]:
                raise Unsupported('object changed while staging for entry link')
            staged_objects.append(str(staged))
        if unit_map is not None:
            build_link_units(source, output, unit_map, external={**metadata, 'objects': staged_objects})
        else:
            info = {'_want_units': True, '_checked_arrays': True}
            code = to_c(source, strict=True, info=info, external=metadata)
            main = _io_main_for(info) if info.get('io') or info.get('ret') == NORET else _main_for(info)
            references = _binding_references(metadata['bindings'], 'ail_object_binding')
            code = ('#define AIL_LINK_STATE(type, name, init) type name init\n'
                    '#define AIL_LINK_EXPORT static\n' + code + references + main)
            c_path = Path(directory) / 'entry.c'
            c_path.write_text(code, encoding='utf8')
            native_diagnostics.generated(c_path, info.get('c_source_regions', info.get('c_units', (None, []))[1]))
            result = native_diagnostics.run([compiler(), *FLAGS, *link_flags(), str(c_path),
                                     *staged_objects, '-o', str(output)]
                                    + (['-lm'] if info.get('libm') else []) + ffi_link_args()
                                    + (['-lws2_32'] if platform.system() == 'Windows'
                                       and {'TCPSOCKET', 'TCPHEAD'}.intersection(
                                           info.get('runtime_parts', []) + metadata['runtime_parts']) else []),
                                    capture_output=True, timeout=120, phase='compile_link')
            if result.returncode:
                raise PipelineError('object entry compile/link failed: ' + result.stderr.decode(errors='replace')[-2000:])
        if load_objects(paths) != metadata:
            raise Unsupported('objects changed during entry build')
    return _finalize_output(output)
