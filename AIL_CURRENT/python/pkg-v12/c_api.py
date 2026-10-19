"""Build an owned, error-returning C interface to a typed AIL source library."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from c_api_runtime import PRELUDE
from module_object import (FLAGS, digest, identity, typed_module, load_objects,
                           _constant_source, _check_external_names, _binding_references)
from pipeline import PipelineError, compiler
import native_diagnostics
from pyfront import Unsupported
from pyfunc import to_c


def declarations(exports, name, tag):
    types = {'int': 'int64_t', 'float': 'double', 'str': name + '_view', 'bytes': name + '_view',
             'array': name + '_int_view', 'list': name + '_int_buffer', 'flist': name + '_float_view', 'noret': 'void'}
    signatures = {}
    for fn, spec in exports.items():
        params = [f'{types[kind]} arg{i}' for i, (_, kind) in enumerate(spec['params'])]
        result = name + '_buffer' if spec['result'] in ('str', 'bytes') else types[spec['result']]
        if spec['result'] == 'flist':
            result = name + '_float_buffer'
        outputs = [] if spec['result'] == 'noret' else [result + ' *out']
        signatures[fn] = f'int {name}_{fn}(' + ', '.join(params + outputs + [name + '_error *error']) + ')'
    header = f'''#ifndef {name}_AIL_LIBRARY_H
#define {name}_AIL_LIBRARY_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {{
#endif
typedef struct {{ const unsigned char *data; size_t size; }} {name}_view;
typedef struct {{ unsigned char *data; size_t size; }} {name}_buffer;
typedef struct {{ const int64_t *data; size_t size; }} {name}_int_view;
typedef struct {{ const double *data; size_t size; }} {name}_float_view;
typedef struct {{ int64_t *data; size_t size; }} {name}_int_buffer;
typedef struct {{ double *data; size_t size; }} {name}_float_buffer;
typedef struct {{ int code; char message[160]; }} {name}_error;
/* 0 success; 1 Value, 2 ZeroDivision, 3 Index, 4 Key, 5 EOF, 6 OS,
   7 Runtime, 8 fatal/allocation, 9 invalid C argument, 10 busy.
   On failure *out is unchanged. Void exports have no out parameter; their int return is status.
   error may be NULL. str is strict UTF-8. Error messages are NUL-terminated prefixes
   of at most 159 bytes; owning str messages stop at a Unicode boundary or embedded NUL.
   Status 8 includes UnicodeDecodeError as well as fatal/allocation failures.
   Inputs borrow valid readable memory for this call. NULL is valid only at size 0.
   Numeric spans count int64_t or double elements; inputs are read-only and properly aligned.
   Successful buffer results belong to the caller; release once with {name}_free.
   Concurrent/reentrant calls return 10; retry only when the active call has ended.
   File/output effects before failure are not rolled back. */
'''
    header += '\n'.join(f'#define {name}_{fn} {name}_{fn}_abi_{tag}' for fn in ('free', *exports)) + '\n'
    header += f'void {name}_free(void *data);\n'
    header += '\n'.join(signature + ';' for signature in signatures.values())
    return header + '\n#ifdef __cplusplus\n}\n#endif\n#endif\n', signatures


def generate(source, name, public=None, external=None, internal=()):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,47}', name) or name.startswith('ail_'):
        raise Unsupported('library name must be an ASCII identifier (1..48 characters), not ail_*')
    tree = ast.parse(source)
    if any(isinstance(n, ast.Name) and n.id == 'sys' or isinstance(n, ast.Call)
           and isinstance(n.func, ast.Name) and n.func.id == 'input' for n in ast.walk(tree)):
        raise Unsupported('C libraries receive input through parameters; input() and sys are unsupported')
    renamed, exports, constants = typed_module(source, integer_lists=True, internal=internal)
    if external:
        _check_external_names(source, {**external['exports'], **external['constants']})
    if not exports:
        raise Unsupported('C library requires at least one typed function')
    selected = set(exports) if public is None else set(public)
    if public is not None and (not public or len(selected) != len(public) or not selected <= exports.keys()):
        raise Unsupported('C exports must name distinct existing functions')
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', fn) or fn in ('free', 'view', 'buffer', 'error', 'int_view', 'int_buffer', 'float_view', 'float_buffer') for fn in selected):
        raise Unsupported('C export names must be ASCII and not an API type or free')
    if any(exports[fn]['result'] == 'tcpsocket' or any(kind == 'tcpsocket' for _, kind in exports[fn]['params']) for fn in selected):
        raise Unsupported('C wrapper exports cannot marshal tcpsocket; use typed native modules')
    if any('handle_list:' in kind for fn in selected
           for kind in (exports[fn]['result'], *(kind for _, kind in exports[fn]['params']))):
        raise Unsupported('C wrapper exports cannot marshal handle lists; use typed native modules')
    names = {spec['symbol']: name + '_private_' + spec['symbol'] for spec in exports.values()}
    class Rename(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            node.name = names.get(node.name, node.name)
            return self.generic_visit(node)

        def visit_Name(self, node):
            node.id = names.get(node.id, node.id)
            return node
    renamed = ast.unparse(Rename().visit(ast.parse(renamed)))
    for spec in exports.values():
        spec['symbol'] = names[spec['symbol']]
    info = {'_want_units': True, '_checked_arrays': True}
    body = to_c(_constant_source(external.get('constants', {})) + renamed if external else renamed,
                strict=True, library=True, info=info, external=external)
    for spec in exports.values():
        if info['function_signatures'][spec['symbol']] != (list(map(tuple, spec['params'])), spec['result']):
            raise Unsupported('C export signature disagrees with inferred types')
        if info['function_array_shapes'][spec['symbol']]:
            raise Unsupported('C integer spans require flat int64 elements, not rows or grids')
        if spec['symbol'] in info['nonflat_list_returns']:
            raise Unsupported('C integer results require flat int64 elements, not rows or handles')
    # Raw generated functions bypass the call guard and ownership boundary. Keep
    # every implementation (including specialized clones) local to this object.
    for _, unit in info['c_units'][1]:
        definitions = [line for line in unit.splitlines() if line.endswith(' {') and not line[0].isspace()]
        if not definitions:
            raise Unsupported('C library function boundary marker changed')
        # a unit is the function and, for a list result, its IR clone (name__irl): each one becomes local
        for first in definitions:
            signature = first[:-2]
            if '__irl(' in signature:         # the clone is emitted `static` already
                if not re.search('^static\n' + re.escape(first) + '$', body, flags=re.MULTILINE):
                    raise Unsupported('C library function boundary marker changed')
                continue
            for ending in (';', ' {'):
                body, count = re.subn('^' + re.escape(signature + ending) + '$',
                                     'static ' + signature + ending, body, flags=re.MULTILINE)
                if count != 1:
                    raise Unsupported('C library function boundary marker changed')
    exports ={fn: spec for fn, spec in exports.items() if fn in selected}
    replacements = {
        'fflush(stdout); fputs(w, stderr); fputc(10, stderr); _Exit(1);':
            'ail_api_trap(ail_exc_kind_of(w) ? ail_exc_kind_of(w) : 8, w);',
    }
    for old, new in replacements.items():
        body, count = re.subn(r'^    ' + re.escape(old) + '$', '    ' + new, body, flags=re.MULTILINE)
        if count != 1:
            raise Unsupported('C library fatal boundary marker changed')
    from c_api_bridge import rewrite_uncaught
    body = rewrite_uncaught(body, 'ail_api_trap')
    body = body.replace('    ail_str_write(s, stderr);\n    fputc(10, stderr);\n    _Exit(1);',
                        '    (void)s; ail_api_trap(8, "assertion failed");')
    tokens = re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '', body, flags=re.DOTALL)
    if '_Exit(' in tokens or '_exit(' in tokens:
        raise Unsupported('unhandled process exit in C library')
    # Every generated runtime state is private and reset before freeing its storage.
    resets = []
    for line in body.splitlines():
        if re.match(r'^\s*#\s*(?:if|ifdef|ifndef|elif|else|endif)\b', line):
            resets.append(line)
            continue
        if not line.startswith('AIL_LINK_STATE('):
            continue
        match = re.match(r'AIL_LINK_STATE\(.+, ([A-Za-z_]\w*)(?:\[[^]]+\])?,\s*(.*?)\);', line)
        if not match or match[2] not in ('', '= 0', '= -1', '= NULL'):
            raise Unsupported('unrecognized C library runtime state')
        variable, initial = match.groups()
        resets.append(f'memset(&{variable}, 0, sizeof {variable});' + (f'{variable} {initial};' if initial else ''))
    dependency_tag = (json.dumps(external['dependencies'], sort_keys=True) +
                      digest(Path(__file__).with_name('c_api_bridge.py'))) if external else ''
    tag = hashlib.sha256((body + PRELUDE + json.dumps(exports, sort_keys=True) + digest(__file__) + dependency_tag).encode()).hexdigest()[:24]
    header, signatures = declarations(exports, name, tag)
    macros = ('malloc', 'calloc', 'realloc', 'free', 'fopen', 'fclose', '_wfopen')
    code = header + PRELUDE + '\n'.join(f'#define {macro} ail_api_{macro.lstrip("_")}' for macro in macros) + '\n'
    if external:
        from c_api_bridge import state_prefix
        code += state_prefix(body, name) + '\n#define AIL_LINK_STATE(type, name, init) type name init\n'
    code += '#define AIL_LINK_EXPORT static\n' + body + '\n' + '\n'.join('#undef ' + macro for macro in macros) + '\n'
    if external:
        from c_api_bridge import library_bridges
        code += library_bridges(name) + _binding_references(external['bindings'], 'ail_api_binding')
    code += 'static void ail_api_reset(void) {\n' + '\n'.join(resets) + '\n}\n'
    code += f'''static int ail_api_error({name}_error *error, int status, const char *message) {{
    if (error) {{ error->code = status; snprintf(error->message, sizeof error->message, "%s", message); }}
    return status;
}}
void {name}_free(void *data) {{ free(data); }}
'''
    if any(spec['result'] == 'str' for spec in exports.values()):
        code += f'''static {name}_buffer ail_api_utf8(ail_str text) {{
    if (text.n < 0 || (uint64_t)text.n > (SIZE_MAX - 1) / 4) ail_api_trap(8, "string too large");
    unsigned char *p = ail_api_malloc((size_t)text.n * 4 + 1);
    size_t n = 0;
    for (int64_t i = 0; i < text.n; i = ail_str_next_unit(text, i)) {{
        uint32_t c = ail_str_point(text, i);
        if (c >= 0xd800 && c <= 0xdfff) ail_api_trap(8, "invalid Unicode result");
        if (c < 0x80) p[n++] = (unsigned char)c;
        else if (c < 0x800) {{ p[n++] = (unsigned char)(0xc0 | (c >> 6)); p[n++] = (unsigned char)(0x80 | (c & 63)); }}
        else if (c < 0x10000) {{ p[n++] = (unsigned char)(0xe0 | (c >> 12)); p[n++] = (unsigned char)(0x80 | ((c >> 6) & 63)); p[n++] = (unsigned char)(0x80 | (c & 63)); }}
        else {{ p[n++] = (unsigned char)(0xf0 | (c >> 18)); p[n++] = (unsigned char)(0x80 | ((c >> 12) & 63)); p[n++] = (unsigned char)(0x80 | ((c >> 6) & 63)); p[n++] = (unsigned char)(0x80 | (c & 63)); }}
    }}
    p[n] = 0;
    return ({name}_buffer){{p, n}};
}}
'''
    for fn, spec in exports.items():
        code += signatures[fn] + ' {\n'
        if spec['result'] != 'noret':
            code += 'if (!out) return ail_api_error(error, 9, "out is NULL");\n'
        for i, (_, kind) in enumerate(spec['params']):
            if kind in ('str', 'bytes'):
                code += f'if ((!arg{i}.data && arg{i}.size) || arg{i}.size > INT64_MAX) return ail_api_error(error, 9, "invalid input span");\n'
            elif kind == 'array':
                code += f'if ((!arg{i}.data && arg{i}.size) || arg{i}.size > INT64_MAX || arg{i}.size > SIZE_MAX / sizeof(int64_t)) return ail_api_error(error, 9, "invalid integer span");\n'
            elif kind == 'flist':
                code += f'if ((!arg{i}.data && arg{i}.size) || arg{i}.size > INT64_MAX || arg{i}.size > SIZE_MAX / sizeof(double) || (arg{i}.size && (uintptr_t)arg{i}.data % _Alignof(double))) return ail_api_error(error, 9, "invalid float span");\n'
        code += 'if (!ail_api_begin()) return ail_api_error(error, 10, "library is busy");\n'
        code += 'if (setjmp(ail_api_jump) == 0) {\n'
        arguments = []
        for i, (_, kind) in enumerate(spec['params']):
            if kind == 'str':
                code += f'ail_sarena arena{i} = {{0}};\nail_str value{i} = ail_utf8_decode_m(&arena{i}, arg{i}.data, (int64_t)arg{i}.size, "invalid UTF-8 input");\n'
                arguments.append(f'value{i}')
            elif kind == 'bytes':
                arguments.append(f'(ail_bytes){{arg{i}.data, (int64_t)arg{i}.size}}')
            elif kind == 'array':
                arguments.extend((f'arg{i}.data', f'(int64_t)arg{i}.size'))
            elif kind == 'flist':
                arguments.append(f'(ail_flist){{(double *)arg{i}.data, (int64_t)arg{i}.size, (int64_t)arg{i}.size}}')
            else:
                arguments.append(f'arg{i}')
        kind = spec['result']
        if kind in ('list', 'flist'):
            arguments.extend(('NULL', '0'))
        call = spec['symbol'] + '(' + ', '.join(arguments) + ')'
        if kind == 'noret':
            code += call + ';\n'
        elif kind == 'str':
            code += f'{name}_buffer result = ail_api_utf8({call});\nail_api_detach(result.data);\n*out = result;\n'
        elif kind == 'bytes':
            code += f'ail_bytes result = {call};\nail_api_detach((void *)result.p);\n*out = ({name}_buffer){{(unsigned char *)result.p, (size_t)result.n}};\n'
        elif kind in ('list', 'flist'):
            element = 'double' if kind == 'flist' else 'int64_t'
            spill = 'ail_fret_spill' if kind == 'flist' else 'ail_ret_spill'
            buffer = 'float_buffer' if kind == 'flist' else 'int_buffer'
            code += f'''int64_t length = {call};
if (length < 0 || (uint64_t)length > SIZE_MAX / sizeof({element}) ||
    (length && ({spill}_n != length || !{spill}_p))) ail_api_trap(8, "invalid numeric result");
{element} *data = length ? {spill}_p : NULL;
ail_api_detach(data);
*out = ({name}_{buffer}){{data, (size_t)length}};
'''
        else:
            code += '*out = ' + call + ';\n'
        code += '}\nint status = ail_api_error(error, ail_api_status, ail_api_message);\nail_api_reset();\nail_api_finish();\nreturn status;\n}\n'
    return header, code, exports, info


def build(source, output, name, public=None, objects=(), internal=(), pic=False):
    output = Path(output)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise Unsupported('library output requires a new directory in an existing parent')
    before = identity()
    pins = {n: digest(Path(__file__).with_name(n)) for n in ('c_api.py', 'c_api_runtime.py', 'c_api_bridge.py')}
    external = load_objects(objects, c_api_namespace=name) if objects else None
    if external:
        pins['c_api_bridge.py'] = digest(Path(__file__).with_name('c_api_bridge.py'))
    header, code, exports, info = generate(source, name, public, external, internal)
    tool_report = None
    with tempfile.TemporaryDirectory(prefix='ail-c-api-') as temporary:
        root = Path(temporary)
        cfile, obj = root / 'library.c', root / (name + '.o')
        cfile.write_text(code, encoding='utf8')
        native_diagnostics.generated(cfile, info.get('c_source_regions', info.get('c_units', (None, []))[1]))
        command = [compiler(), *FLAGS, *(['-fPIC', '-fvisibility=hidden'] if pic else []), '-std=gnu11', '-c', str(cfile), '-o', str(obj)]
        result = native_diagnostics.run(command, phase='compile', capture_output=True, timeout=180)
        if result.returncode:
            raise PipelineError('C library compile failed: ' + result.stderr.decode(errors='replace')[-4000:])
        if external:
            staged = []
            for index, original in enumerate(external['objects']):
                path = root / f'dependency{index}.o'
                path.write_bytes(Path(original).read_bytes())
                if digest(path) != external['object_hashes'][original]:
                    raise Unsupported('dependency object changed while staging')
                staged.append(str(path))
            combined = root / 'combined.o'
            result = native_diagnostics.run([compiler(), '-r', str(obj), *staged, '-o', str(combined)],
                                    capture_output=True, timeout=180, phase='link')
            if result.returncode:
                raise PipelineError('C library object combine failed: ' + result.stderr.decode(errors='replace')[-4000:])
            query = subprocess.run([compiler(), '-print-prog-name=objcopy'], capture_output=True,
                                   timeout=20, check=True)
            tool = query.stdout.decode().strip()
            try:
                tool = Path(shutil.which(tool) or tool).resolve(strict=True)
            except FileNotFoundError:
                raise Unsupported('a C library build needs an ELF/COFF objcopy to localize symbols and none was '
                                  'found (%s is not installed; the Apple toolchain has no objcopy)' % tool) from None
            tool_hash = digest(tool)
            public_symbols = re.findall(r'^#define ' + re.escape(name) + r'_\w+ (\w+_abi_[0-9a-f]{24})$',
                                        header, re.MULTILINE)
            if len(public_symbols) != len(exports) + 1:
                raise Unsupported('C library public symbol marker changed')
            argv = [str(tool), *(f'--keep-global-symbol={symbol}' for symbol in public_symbols),
                    str(combined), str(obj)]
            result = native_diagnostics.run(argv, phase='object_symbols', capture_output=True, timeout=180)
            if result.returncode:
                raise PipelineError('C library symbol localization failed: ' + result.stderr.decode(errors='replace')[-4000:])
            if digest(tool) != tool_hash:
                raise Unsupported('objcopy changed during library build')
            tool_report = dict(path=str(tool), sha256=tool_hash, argv=argv, returncode=result.returncode)
            if load_objects(objects, c_api_namespace=name) != external:
                raise Unsupported('dependency objects changed during library build')
        if identity() != before or pins != {n: digest(Path(__file__).with_name(n)) for n in pins}:
            raise Unsupported('compiler/runtime identity changed during library build')
        if tool_report and digest(Path(tool_report['path'])) != tool_report['sha256']:
            raise Unsupported('objcopy changed before library publication')
        output.mkdir()
        (output / (name + '.h')).write_text(header, encoding='utf8')
        (output / obj.name).write_bytes(obj.read_bytes())
        report = dict(schema=1, name=name, exports=exports, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                      identity=before, build_flags=FLAGS + ['-std=gnu11'],
                      link_libraries=(['m'] if info.get('libm') else [])
                          + (['ws2_32'] if os.name == 'nt' and {'TCPSOCKET', 'TCPHEAD'}.intersection(info.get('runtime_parts', [])) else []),
                      code_sha256=pins,
                      sha256={n: digest(output / n) for n in (name + '.h', name + '.o')})
        if external:
            report.update(c_api_namespace=name, dependencies=external['dependencies'],
                          object_hashes=external['object_hashes'], objcopy=tool_report)
        (output / 'library.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--name', required=True)
    parser.add_argument('-o', '--output', type=Path, required=True)
    parser.add_argument('--export', action='append')
    parser.add_argument('--object', action='append', type=Path, default=[])
    parser.add_argument('--native-report', help=argparse.SUPPRESS)
    parser.add_argument('--native-debug-dir', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.native_report:
        native_diagnostics.configure(args.native_report, args.native_debug_dir)
    try:
        print(json.dumps(build(args.source.read_text(encoding='utf8'), args.output, args.name, args.export, objects=args.object)))
    except (ValueError, Unsupported, PipelineError, OSError) as error:
        native_diagnostics.failure(error)
        parser.exit(1, str(error) + '\n')
