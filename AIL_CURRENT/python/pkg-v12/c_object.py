"""Compile trusted C functions and declared headers behind typed AIL object adapters."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

import cruntime
from module_object import ABI_VERSION, FLAGS, canonical, contract_symbol, digest, identity, _valid_name
from pipeline import PipelineError, compiler
import native_diagnostics
from pyfront import Unsupported

C_KEYWORDS = set(('auto break case char const continue default do double else enum extern float '
                  'for goto if inline int long register restrict return short signed sizeof static '
                  'struct switch typedef union unsigned void volatile while _Alignas _Alignof '
                  '_Atomic _Bool _Complex _Generic _Imaginary _Noreturn _Static_assert _Thread_local').split())
C_INTEGERS = {kind: (kind+'_t', kind.upper()+'_MIN' if kind.startswith('int') else '0', kind.upper()+'_MAX')
              for kind in ('int8','uint8','int16','uint16','int32','uint32')}
C_KINDS = ('int', 'bool', 'uint64_bits', 'float', 'float32', 'str', 'bytes', 'list', 'float_list', 'float32_list') + tuple(C_INTEGERS)
C_INPUT_KINDS = C_KINDS + ('borrowed_bytes', 'cstr')


def _c_name(name):
    return (isinstance(name, str) and bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name))
            and name not in C_KEYWORDS and not name.startswith('ail_'))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate interface key: ' + key)
        result[key] = value
    return result


def _local_names(value, suffixes=('h', 'inc'), label='headers'):
    if not isinstance(value, list):
        raise ValueError('C ' + label + ' must be a list of relative paths')
    reserved = {'con', 'prn', 'aux', 'nul'} | {f'{prefix}{i}' for prefix in ('com', 'lpt') for i in range(1, 10)}
    names = set()
    for name in value:
        if (not isinstance(name, str)
                or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*\.(?:' + '|'.join(suffixes) + ')', name)
                or any(part.endswith('.') or part.split('.')[0].lower() in reserved for part in name.split('/'))):
            raise ValueError('invalid C ' + label + ' path')
        key = name.lower()
        if key in names or any(key.startswith(other + '/') or other.startswith(key + '/') for other in names):
            raise ValueError('duplicate or conflicting C ' + label + ' paths')
        names.add(key)


def read_interface(path):
    raw = Path(path).read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=_pairs)
        if (not isinstance(value, dict) or set(value) - {'version', 'functions', 'libm', 'headers', 'sources', 'asm_sources', 'archives'}
                or type(value.get('version')) is not int or value['version'] != 1
                or type(value.get('libm', False)) is not bool
                or not isinstance(value.get('functions'), dict)
                or not value['functions']):
            raise ValueError('invalid C interface schema')
        _local_names(value.get('headers', []))
        _local_names(value.get('sources', []), ('c',), 'sources')
        _local_names(value.get('asm_sources', []), ('S',), 'asm_sources')
        _local_names(value.get('archives', []), ('a',), 'archives')
        _local_names(value.get('headers', []) + value.get('sources', []) + value.get('asm_sources', [])
                     + value.get('archives', []), ('h', 'inc', 'c', 'S', 'a'), 'inputs')
        symbols = set()
        for name, fn in value['functions'].items():
            if (not _valid_name(name) or not isinstance(fn, dict)
                    or set(fn) != {'symbol', 'params', 'result'} or not _c_name(fn['symbol'])
                    or fn['symbol'] in symbols or fn['result'] not in C_KINDS + ('void',)
                    or not isinstance(fn['params'], list)):
                raise ValueError('invalid C interface function: ' + name)
            symbols.add(fn['symbol'])
            names = set()
            for param in fn['params']:
                if (not isinstance(param, list) or len(param) != 2 or not _valid_name(param[0])
                        or param[0] in names or param[1] not in C_INPUT_KINDS):
                    raise ValueError('invalid C interface parameter')
                names.add(param[0])
        return value
    except (ValueError, TypeError, UnicodeError) as error:
        raise Unsupported(str(error)) from error


def _system_header_roots(environment):
    result = subprocess.run([compiler(), '-E', '-x', 'c', '-', '-v'], input=b'',
                            capture_output=True, timeout=30, env=environment)
    listing = result.stderr.decode(errors='replace')
    start, end = '#include <...> search starts here:', 'End of search list.'
    if result.returncode or start not in listing or end not in listing:
        raise PipelineError('cannot identify compiler system header directories')
    return [Path(line.strip()).resolve() for line in listing.split(start, 1)[1].split(end, 1)[0].splitlines()
            if line.strip()]


def _dependency_paths(text, directory):
    body = text.replace('\\\n', '').split(':', 1)[-1]
    return [(Path(directory) / re.sub(r'\\(.)', r'\1', token).replace('$$', '$')).resolve()
            for token in re.findall(r'(?:\\.|[^\s])+', body)]


ENCODER = r'''
static size_t ail_c_encode(ail_str s, unsigned char *out) {
    if (s.n > 0) memcpy(out, s.p, (size_t)s.n);   /* a str is UTF-8 already */
    return (size_t)s.n;
}
'''


def compile_c(source_path, interface_path, output, *, c_api_namespace=None):
    source = Path(source_path).read_text(encoding='utf8')
    interface = read_interface(interface_path)
    if c_api_namespace is not None:
        from c_api_bridge import validate_namespace
        validate_namespace(c_api_namespace)
        if interface.get('asm_sources'):
            raise Unsupported('C API dependencies require C sources; assembly resource management is unsupported')
    source_root = Path(source_path).resolve().parent
    headers, sources, assembly, archives = {}, {}, {}, {}
    for name in interface.get('headers', []) + interface.get('sources', []) + interface.get('asm_sources', []) + interface.get('archives', []):
        try:
            path = (source_root / name).resolve(strict=True)
            if not path.is_relative_to(source_root):
                raise Unsupported('C input resolves outside the source directory')
            if name in interface.get('archives', []):
                data = path.read_bytes()
                if not data.startswith(b'!<arch>\n'):
                    raise Unsupported('C archives must be regular self-contained archives; thin archives are unsupported')
                archives[name] = data
            elif name in interface.get('sources', []) + interface.get('asm_sources', []):
                if path == Path(source_path).resolve():
                    raise Unsupported('C sources must not repeat the primary source')
                (assembly if name in interface.get('asm_sources', []) else sources)[name] = path.read_bytes()
            else:
                headers[name] = path.read_bytes()
        except (OSError, RuntimeError) as error:
            raise Unsupported('cannot read declared C input: ' + name) from error
    output = Path(output).resolve()
    metadata = Path(str(output) + '.json')
    if output.exists() or metadata.exists() or output.is_symlink() or metadata.is_symlink():
        raise Unsupported('object output or its metadata already exists')
    before = identity()
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() not in {'CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'OBJC_INCLUDE_PATH'}}
    environment['LC_ALL'] = 'C'
    system_roots = _system_header_roots(environment)
    inputs = headers | sources | assembly | archives
    header_identity = canonical({name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()}) if inputs else b''
    binding_tools = None
    if archives and c_api_namespace is not None:
        from c_api_bridge import archive_tools
        binding_tools = archive_tools(environment)
        header_identity += canonical({name: tool['sha256'] for name, tool in binding_tools.items()})
    prefix = 'ail_object_' + hashlib.sha256(source.encode() + canonical(interface) + header_identity).hexdigest()[:24] + '_'
    if c_api_namespace is not None:
        prefix = c_api_namespace + '_ail_dependency_' + prefix
    native_prefix = prefix.replace('ail_object_', 'ail_cnative_', 1)
    types = {'int': 'int64_t', 'bool': 'int64_t', 'uint64_bits': 'int64_t', 'float': 'double', 'float32': 'double', 'str': 'ail_str', 'cstr': 'ail_str', 'bytes': 'ail_bytes', 'borrowed_bytes': 'ail_bytes',
             'list': 'int64_t', 'float_list': 'ail_flist', 'float32_list': 'ail_flist', 'void': 'void', **dict.fromkeys(C_INTEGERS, 'int64_t')}
    c_types = types | {'bool': '_Bool', 'float32': 'float', 'uint64_bits': 'uint64_t'} | {kind: spec[0] for kind, spec in C_INTEGERS.items()}
    exports, wrappers, checks, prototypes = {}, [], [], []
    has_str = any(kind in ('str', 'cstr') for fn in interface['functions'].values() for _, kind in fn['params'])
    has_bytes = any(kind in ('bytes', 'borrowed_bytes') for fn in interface['functions'].values() for _, kind in fn['params'])
    has_borrowed_bytes = any(kind == 'borrowed_bytes' for fn in interface['functions'].values() for _, kind in fn['params'])
    has_lists = any(kind == 'list' for fn in interface['functions'].values() for _, kind in fn['params'])
    has_float_lists = any(kind in ('float_list', 'float32_list') for fn in interface['functions'].values() for _, kind in fn['params'])
    has_narrow = any(kind in C_INTEGERS or kind == 'bool' for fn in interface['functions'].values() for _, kind in fn['params'])
    has_float32 = any(fn['result'] in ('float32', 'float32_list') or any(kind in ('float32', 'float32_list') for _, kind in fn['params'])
                      for fn in interface['functions'].values())
    returns_bytes = any(fn['result'] == 'bytes' for fn in interface['functions'].values())
    returns_str = any(fn['result'] == 'str' for fn in interface['functions'].values())
    returns_list = any(fn['result'] == 'list' for fn in interface['functions'].values())
    returns_float_list = any(fn['result'] in ('float_list', 'float32_list') for fn in interface['functions'].values())
    for name, fn in interface['functions'].items():
        params = fn['params']
        owned_bytes = fn['result'] == 'bytes'
        owned_str = fn['result'] == 'str'
        owned_list = fn['result'] in ('list', 'float_list', 'float32_list')
        narrow_result = fn['result'] == 'float32_list'
        float_result = fn['result'] in ('float_list', 'float32_list')
        element = 'double' if float_result else 'int64_t'
        list_type = 'ail_flist' if float_result else 'ail_list'
        spill = 'ail_fret_spill_p' if float_result else 'ail_ret_spill_p'
        owned = owned_bytes or owned_str or owned_list
        foreign_result = ('ail_c_float32_view' if narrow_result else 'ail_c_float_view' if float_result else 'ail_c_int_view' if owned_list else 'ail_c_utf8_view' if owned_str
                          else 'ail_c_bytes_view') if owned else c_types[fn['result']]
        exports[name] = dict(params=[[p, 'int' if kind in C_INTEGERS or kind in ('bool', 'uint64_bits') else {'list': 'array', 'float_list': 'flist', 'float32_list': 'flist', 'float32': 'float', 'borrowed_bytes': 'bytes', 'cstr': 'str'}.get(kind, kind)] for p, kind in params],
                             result='noret' if fn['result'] == 'void' else 'int' if fn['result'] in C_INTEGERS or fn['result'] in ('bool', 'uint64_bits') else 'flist' if float_result else 'float' if fn['result'] == 'float32' else fn['result'],
                             symbol=prefix + name, owned_str=owned_str, owned_bytes=owned_bytes)
        foreign_types = [t for _, kind in params for t in
                         (['const char *'] if kind == 'cstr' else ['const unsigned char *', 'size_t'] if kind in ('str', 'bytes', 'borrowed_bytes')
                          else ['const int64_t *', 'size_t'] if kind == 'list'
                          else ['const float *', 'size_t'] if kind == 'float32_list'
                          else ['const double *', 'size_t'] if kind == 'float_list' else [c_types[kind]])]
        checks.append('_Static_assert(_Generic(&%s, %s (*)(%s): 1, default: 0), "C prototype mismatch");'
                      % (fn['symbol'], foreign_result, ', '.join(foreign_types) or 'void'))
        prototypes.append('%s %s(%s);' % (foreign_result, fn['symbol'], ', '.join(foreign_types) or 'void'))
        declarations = ', '.join('const int64_t *p%d, int64_t p%d_n' % (i, i) if kind == 'list'
                                 else types[kind] + ' p%d' % i for i, (_, kind) in enumerate(params))
        if owned_list:
            declarations += (', ' if declarations else '') + element + ' *_out, int64_t _cap'
        declarations = declarations or 'void'
        lines, args, strings, floats = [], [], [], []
        if owned_list:
            lines.append(f'if (_cap < 0 || (uint64_t)_cap > SIZE_MAX / sizeof({element}) || (!_out && _cap) || (_cap && (uintptr_t)_out % _Alignof({element}))) ail_die("invalid C list output");')
        for i, (_, kind) in enumerate(params):
            if kind == 'borrowed_bytes':
                lines.append(f'if (p{i}.n < 0 || (uint64_t)p{i}.n > SIZE_MAX || (!p{i}.p && p{i}.n)) ail_die("invalid C borrowed bytes span");')
                args.extend([f'p{i}.p', f'(size_t)p{i}.n'])
                continue
            if kind == 'float32_list':
                lines += [f'if (p{i}.n < 0 || (uint64_t)p{i}.n > SIZE_MAX / sizeof(double) || (!p{i}.p && p{i}.n) || (p{i}.n && (uintptr_t)p{i}.p % _Alignof(double))) ail_die("invalid C float span");',
                          f'for (int64_t j = 0; j < p{i}.n; ++j) if (!(p{i}.p[j] >= -FLT_MAX && p{i}.p[j] <= FLT_MAX)) ail_die("C float32 argument out of range");',
                          f'if ((uint64_t)p{i}.n > (SIZE_MAX - cap) / sizeof(float)) ail_die("C float32 size overflow");',
                          f'cap += (size_t)p{i}.n * sizeof(float);']
                floats.append(i)
                args.extend([f'f{i}', f'(size_t)p{i}.n'])
                continue
            if kind == 'float32':
                lines.append(f'if (!(p{i} >= -FLT_MAX && p{i} <= FLT_MAX)) ail_die("C float32 argument out of range");')
                args.append(f'(float)p{i}')
                continue
            if kind == 'uint64_bits':
                args.append(f'(uint64_t)p{i}')
                continue
            if kind == 'bool':
                lines.append(f'if (p{i} != 0 && p{i} != 1) ail_die("C bool argument out of range");')
                args.append(f'(_Bool)p{i}')
                continue
            if kind in C_INTEGERS:
                c_type, lower, upper = C_INTEGERS[kind]
                lines.append(f'if (p{i} < {lower} || p{i} > {upper}) ail_die("C {kind} argument out of range");')
                args.append(f'({c_type})p{i}')
                continue
            if kind == 'float_list':
                lines.append('if (p%d.n < 0 || (uint64_t)p%d.n > SIZE_MAX / sizeof(double) || (!p%d.p && p%d.n) || (p%d.n && (uintptr_t)p%d.p %% _Alignof(double))) ail_die("invalid C float span");' % (i, i, i, i, i, i))
                args.extend(['p%d.p' % i, '(size_t)p%d.n' % i])
                continue
            if kind == 'list':
                lines.append('if (p%d_n < 0 || (uint64_t)p%d_n > SIZE_MAX / sizeof(int64_t) || (!p%d && p%d_n)) ail_die("invalid C integer span");' % (i, i, i, i))
                args.extend(['p%d' % i, '(size_t)p%d_n' % i])
                continue
            if kind not in ('str', 'cstr', 'bytes'):
                args.append('p%d' % i)
                continue
            strings.append((i, kind))
            width = 3 if kind in ('str', 'cstr') else 1
            if kind == 'cstr':
                lines.append('if (cap == SIZE_MAX) ail_die("C string size overflow");')
                lines.append('cap += 1;')
            lines.append('if (p%d.n < 0 || (uint64_t)p%d.n > (SIZE_MAX - cap) / %d) ail_die("C %s size overflow");' % (i, i, width, 'string' if kind in ('str', 'cstr') else 'bytes'))
            if kind == 'bytes':
                lines.append(f'if (!p{i}.p && p{i}.n) ail_die("invalid C bytes span");')
            lines.append('cap += (size_t)p%d.n * %d;' % (i, width))
            args.extend([f'(const char *)b{i}'] if kind == 'cstr' else ['b%d' % i, 'n%d' % i])
        buffered = bool(strings or floats)
        if buffered:
            lines = ['size_t cap = 1;'] + lines + ['unsigned char *buffer = malloc(cap);',
                    'if (!buffer) ail_die("out of memory");', 'size_t offset = 0;']
            for i in floats:
                lines += [f'float *f{i} = (float *)(buffer + offset);',
                          f'for (int64_t j = 0; j < p{i}.n; ++j) f{i}[j] = (float)p{i}.p[j];',
                          f'offset += (size_t)p{i}.n * sizeof(float);']
            for i, kind in strings:
                lines.append('unsigned char *b%d = buffer + offset;' % i)
                if kind in ('str', 'cstr'):
                    lines.append('size_t n%d = ail_c_encode(p%d, b%d);' % (i, i, i))
                else:
                    lines += ['size_t n%d = (size_t)p%d.n;' % (i, i),
                              'if (n%d > 0) memcpy(b%d, p%d.p, n%d);' % (i, i, i, i)]
                lines.append('offset += n%d;' % i)
                if kind == 'cstr':
                    lines += [f'if (memchr(b{i}, 0, n{i})) {{ free(buffer); ail_die("C cstr contains NUL"); }}',
                              'buffer[offset++] = 0;']
        call = '%s(%s);' % (native_prefix + fn['symbol'], ', '.join(args))
        lines.append(call if fn['result'] == 'void' else '%s %s = %s' % (foreign_result, 'borrowed' if owned else 'result', call))
        if owned:
            cleanup = 'free(buffer); ' if buffered else ''
            list_check = (f' || borrowed.size > SIZE_MAX / sizeof({element}) || '
                          f'(borrowed.size && (uintptr_t)borrowed.data % _Alignof({"float" if narrow_result else element}))') if owned_list else ''
            lines += ['if (borrowed.size > INT64_MAX || (!borrowed.data && borrowed.size)' + list_check + ') { '
                      + cleanup + 'ail_die("invalid C %s result"); }' % fn['result']]
            if narrow_result:
                lines += ['for (size_t j = 0; j < borrowed.size; ++j) if (!(borrowed.data[j] >= -FLT_MAX && borrowed.data[j] <= FLT_MAX)) { '+cleanup+'ail_die("C float32 result is not finite"); }',
                          'double *wide = malloc(borrowed.size ? borrowed.size * sizeof(double) : 1);',
                          'if (!wide) { '+cleanup+'ail_die("out of memory"); }',
                          'for (size_t j = 0; j < borrowed.size; ++j) wide[j] = (double)borrowed.data[j];']
                if buffered:
                    lines.append('free(buffer);')
                lines += ['ail_flist view = {wide, (int64_t)borrowed.size, (int64_t)borrowed.size};',
                          'int64_t result = ail_flist_return(&view, _out, _cap);', 'free(wide);']
            elif owned_list:
                lines += [f'{list_type} view = {{({element} *)borrowed.data, (int64_t)borrowed.size, (int64_t)borrowed.size}};',
                          'int64_t result = view.n;',
                          'if (result > _cap) {',
                          f'{list_type}_return(&view, NULL, 0);',
                          f'if (_cap) memmove(_out, {spill}, (size_t)_cap * sizeof({element}));',
                          '} else if (result) {',
                          f'memmove(_out, borrowed.data, (size_t)result * sizeof({element}));',
                          '}']
            elif owned_str:
                lines += ['ail_sarena arena = {0};',
                          'ail_str decoded = ail_utf8_decode_m(&arena, borrowed.data, (int64_t)borrowed.size, "C result is not valid UTF-8");',
                          'ail_str result = ail_str_return_owned(decoded);',
                          'ail_sarena_free(&arena);']
            else:
                lines.append('ail_bytes result = ail_bytes_return_owned((ail_bytes){borrowed.data, (int64_t)borrowed.size});')
        if buffered and not narrow_result:
            lines.append('free(buffer);')
        if fn['result'] == 'float32':
            lines.append('if (!(result >= -FLT_MAX && result <= FLT_MAX)) ail_die("C float32 result is not finite");')
        lines.append('return result <= INT64_MAX ? (int64_t)result : -1 - (int64_t)(UINT64_MAX - result);'
                     if fn['result'] == 'uint64_bits' else 'return;' if fn['result'] == 'void' else 'return result;')
        wrappers.append('%s %s(%s) {\n%s\n}' % ('int64_t' if owned_list else types[fn['result']], prefix + name, declarations, '\n'.join(lines)))
    parts = ((['DIE'] if has_lists or has_narrow or has_float32 or has_borrowed_bytes else []) + (['STR'] if has_str else []) + (['BYTES'] if has_bytes else [])
             + (['FLIST'] if has_float_lists else [])
             + (['BYTESRET'] if returns_bytes else []) + (['STRRET'] if returns_str else [])
             + (['LISTRET'] if returns_list else []) + (['FLISTRET'] if returns_float_list else []))
    # String inputs reach C only as temporary copies; numeric results cannot carry
    # AIL string references. This describes arena lifetime, not C side effects.
    contract = dict(version=ABI_VERSION, exports=exports, constants={}, structs={}, runtime_parts=parts, dependencies=[],
                    readonly_scalar_helpers=[],
                    non_escaping_string_helpers=sorted(name for name, spec in exports.items()
                                                       if spec['result'] in {'int', 'float', 'list', 'flist'}
                                                       and any(kind == 'str' for _, kind in spec['params'])),
                    libm=interface.get('libm', False), io=False, identity=before)
    if c_api_namespace is not None:
        contract['c_api_namespace'] = c_api_namespace
    preamble = ('#include <stdint.h>\n#include <stddef.h>\n#include <stdlib.h>\n#include <stdio.h>\n'
            + ('#include <float.h>\n#include <limits.h>\n'
               '_Static_assert(CHAR_BIT == 8 && sizeof(float) == 4 && FLT_RADIX == 2 && '
               'FLT_MANT_DIG == 24 && FLT_MIN_EXP == -125 && FLT_MAX_EXP == 128 && FLT_HAS_SUBNORM == 1, '
               '"C float32 requires binary32 with subnormals");\n' if has_float32 else '')
            + ('typedef struct { const unsigned char *data; size_t size; } ail_c_bytes_view;\n' if returns_bytes else '')
            + ('typedef struct { const unsigned char *data; size_t size; } ail_c_utf8_view;\n' if returns_str else '')
            + ('typedef struct { const int64_t *data; size_t size; } ail_c_int_view;\n' if returns_list else '')
            + ('typedef struct { const double *data; size_t size; } ail_c_float_view;\n' if returns_float_list else '')
            + ('typedef struct { const float *data; size_t size; } ail_c_float32_view;\n' if any(fn['result'] == 'float32_list' for fn in interface['functions'].values()) else '')
            + ''.join('#define %s %s\n' % (fn['symbol'], native_prefix + fn['symbol'])
                      for fn in interface['functions'].values()))
    code = (preamble + source + '\n' + '\n'.join(checks)
            + '\n' + ''.join('#undef %s\n' % fn['symbol'] for fn in interface['functions'].values())
            + '\n#define AIL_LINK_STATE(type, name, init) extern type name\n#define AIL_LINK_EXPORT static\n'
            + cruntime.emit(parts) + (ENCODER if has_str else '') + '\n'.join(wrappers)
            + '\nconst unsigned char ' + contract_symbol(contract) + ' = 0;\n')
    if c_api_namespace is not None:
        from c_api_bridge import object_prefix, resource_prefix
        code = object_prefix(code, c_api_namespace)
    with tempfile.TemporaryDirectory(prefix='ail-c-object-') as directory:
        c_path, target = (Path(directory) / name for name in ('adapter.c', 'adapter.o'))
        c_path.write_text(code, encoding='utf8')
        native_diagnostics.generated(c_path)
        input_root = Path(directory) / 'inputs'
        input_root.mkdir()
        for name, data in inputs.items():
            header = input_root / name
            header.parent.mkdir(parents=True, exist_ok=True)
            header.write_bytes(((resource_prefix(c_api_namespace) if c_api_namespace is not None else '')
                               + preamble + '\n'.join(prototypes) + '\n').encode() + data if name in sources else data)
        units = [c_path, *(input_root / name for name in sources), *(input_root / name for name in assembly)]
        objects = []
        for index, unit in enumerate(units):
            obj, depfile = (Path(directory) / f'unit{index}.{suffix}' for suffix in ('o', 'd'))
            is_assembly = unit.suffix == '.S'
            gas_depfile = obj.with_suffix('.gas.d')
            options = (['-x', 'assembler-with-cpp', '-save-temps=obj', '-Wa,--MD,' + str(gas_depfile), '-Wa,-I,inputs']
                       + ['-D' + fn['symbol'] + '=' + native_prefix + fn['symbol'] for fn in interface['functions'].values()]
                       if is_assembly else ['-std=c11', '-Werror=strict-prototypes', '-Werror=old-style-definition'])
            if unit != c_path:
                native_diagnostics.generated(unit)
            result = native_diagnostics.run([compiler(), *FLAGS, *options, '-MD', '-MF', str(depfile), '-MT', 'unit',
                                 '-I', 'inputs', '-c', unit.relative_to(directory).as_posix(), '-o',
                                 obj.relative_to(directory).as_posix() if is_assembly else str(obj)], cwd=directory,
                                capture_output=True, timeout=120, env=environment, phase='compile')
            if result.returncode:
                raise PipelineError('C adapter compile failed: ' + result.stderr.decode(errors='replace')[-2000:])
            # Each translation unit can include only declared headers and system headers.
            dependencies = _dependency_paths(depfile.read_text(), directory)
            allowed = {unit.resolve()} | {(input_root / name).resolve() for name in headers}
            if is_assembly:
                dependencies += _dependency_paths(gas_depfile.read_text(), directory)
                allowed.add(obj.with_suffix('.s').resolve())
            if not dependencies or any(path not in allowed and not any(path.is_relative_to(root) for root in system_roots)
                                   for path in dependencies):
                raise Unsupported('C adapters require self-contained source, declared headers and system headers only')
            objects.append(obj)
        if binding_tools is not None:
            from c_api_bridge import bind_archive_resources
            bind_archive_resources(objects[0], c_api_namespace, prefix, binding_tools, environment,
                                   archives=[input_root / name for name in archives])
        if sources or assembly or archives:
            archive_args = (['-Wl,--start-group', *(str(input_root / name) for name in archives),
                             '-Wl,--end-group'] if archives else [])
            result = native_diagnostics.run([compiler(), '-r', *map(str, objects), *archive_args, '-o', str(target)], cwd=directory,
                                    capture_output=True, timeout=120, env=environment, phase='link')
            if result.returncode:
                raise PipelineError('C objects combine failed: ' + result.stderr.decode(errors='replace')[-2000:])
        else:
            target = objects[0]
        if binding_tools is not None:
            from c_api_bridge import bind_archive_resources
            bind_archive_resources(target, c_api_namespace, prefix, binding_tools, environment)
        if identity() != before:
            raise Unsupported('compiler/runtime identity changed during C object build')
        created = metadata_created = False
        try:
            with output.open('xb') as destination:
                created = True
                destination.write(target.read_bytes())
            with metadata.open('x', encoding='utf8') as destination:
                metadata_created = True
                destination.write(json.dumps(dict(contract=contract, object_sha256=digest(target)), indent=2) + '\n')
        except Exception:
            if metadata_created:
                metadata.unlink()
            if created:
                output.unlink()
            raise
    return output
