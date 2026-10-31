"""Build lib<name>.so, lib<name>.a and <name>.h from the output of ail_export.lower().

The typed C library core (c_api.py) already isolates every call: a failure becomes a status and a
message instead of an exit, results are malloc'd and owned by the caller, and no state survives a
call. This module adds the public face a C, Rust or ctypes host expects:

    int  <name>_<fn>(args..., result out-parameters)     0 on success, else a NAME_ERR_* status
    const char *<name>_last_error(void)                  "ValueError: text" of this thread's last failure
    void <name>_free(void *)                             releases str / bytes / list results

Calls are serialized by one mutex, so any thread may call at any time; there is nothing to
initialize or tear down. The status table, ownership and type mapping are written into the header.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

import c_api
from module_object import FLAGS
from pipeline import PipelineError, compiler
import native_diagnostics
from pyfront import Unsupported

STATUS = (('OK', 0, ''), ('VALUE', 1, 'ValueError'), ('ZERO_DIVISION', 2, 'ZeroDivisionError'), ('INDEX', 3, 'IndexError'),
          ('KEY', 4, 'KeyError'), ('EOF', 5, 'EOFError'), ('OS', 6, 'OSError'), ('RUNTIME', 7, 'RuntimeError'),
          ('INTERNAL', 8, 'InternalError'), ('ARGUMENT', 9, 'InvalidArgument'))
C_KEYWORDS = set('auto break case char const continue default do double else enum extern float for goto if inline int long '
                 'register restrict return short signed sizeof static struct switch typedef union unsigned void volatile '
                 'while bool true false'.split())
SCALAR_C = {'int': 'int64_t', 'float': 'double', 'bool': 'bool'}
ARRAY_C = {'bytes': 'uint8_t', 'ints': 'int64_t', 'floats': 'double'}


def _unique(name, used):
    name = name + '_' if name in C_KEYWORDS else name
    while name in used:
        name += '_'
    used.add(name)
    return name


def _signature(name, export, structs):
    """(C parameter declarations, C result declarations, python-ish doc line)."""
    used = set()
    params, call, checks = [], [], []
    core = name + '_core'
    for p in export['params']:
        n = _unique(p['name'], used)
        kind = p['kind']
        if kind in SCALAR_C:
            params.append('%s %s' % (SCALAR_C[kind], n))
            call.append('(int64_t)%s' % n if kind == 'bool' else n)
        elif kind == 'str':
            params.append('const char *%s' % n)
            checks.append('if (!%s) return %s_fail(NAME_ERR_ARGUMENT, "NULL string argument %s");' % (n, name, p['name']))
            call.append('(%s_view){(const unsigned char *)%s, strlen(%s)}' % (core, n, n))
        elif kind in ARRAY_C:
            length = _unique(n + '_len', used)
            ctype = ARRAY_C[kind]
            params.append('const %s *%s' % (ctype, n))
            params.append('size_t %s' % length)
            checks.append('if ((!%s && %s) || (%s && (uintptr_t)%s %% _Alignof(%s))) return %s_fail(NAME_ERR_ARGUMENT, '
                          '"invalid span %s");' % (n, length, n, n, ctype, name, p['name']))
            wrapper = {'bytes': '%s_view' % core, 'ints': '%s_int_view' % core, 'floats': '%s_float_view' % core}[kind]
            cast = '(const unsigned char *)' if kind == 'bytes' else ''
            call.append('(%s){%s%s, %s}' % (wrapper, cast, n, length))
        else:
            params.append('const %s_%s *%s' % (name, p['type'], n))
            checks.append('if (!%s) return %s_fail(NAME_ERR_ARGUMENT, "NULL struct argument %s");' % (n, name, p['name']))
            for f in structs[p['type']]:
                call.append('(int64_t)%s->%s' % (n, f['name']) if f['kind'] == 'bool' else '%s->%s' % (n, f['name']))
    result = export['result']['kind']
    outs, finish = [], []
    if result == 'void':
        core_out = None
    elif result in SCALAR_C:
        out = _unique('out', used)
        outs.append('%s *%s' % (SCALAR_C[result], out))
        checks.insert(0, 'if (!%s) return %s_fail(NAME_ERR_ARGUMENT, "out is NULL");' % (out, name))
        core_out = 'int64_t' if result != 'float' else 'double'
        finish.append('*%s = %s;' % (out, 'value != 0' if result == 'bool' else 'value'))
    elif result == 'str':
        out = _unique('out', used)
        outs.append('char **%s' % out)
        checks.insert(0, 'if (!%s) return %s_fail(NAME_ERR_ARGUMENT, "out is NULL");' % (out, name))
        core_out = '%s_buffer' % core
        finish.append('if (strlen((const char *)value.data) != value.size) { %s_core_free(value.data); '
                      'return %s_fail(NAME_ERR_VALUE, "str result contains a NUL character; return bytes"); }' % (name, name))
        finish.append('*%s = (char *)value.data;' % out)
    else:
        out = _unique('out', used)
        length = _unique(out + '_len', used)
        ctype = ARRAY_C[result]
        outs.append('%s **%s' % (ctype, out))
        outs.append('size_t *%s' % length)
        checks.insert(0, 'if (!%s || !%s) return %s_fail(NAME_ERR_ARGUMENT, "out is NULL");' % (out, length, name))
        core_out = {'bytes': '%s_buffer' % core, 'ints': '%s_int_buffer' % core, 'floats': '%s_float_buffer' % core}[result]
        finish.append('*%s = (%s *)value.data; *%s = value.size;' % (out, ctype, length))
    return params, outs, checks, call, core_out, finish


def _c_type_doc(kind, type_name=None):
    return {'int': 'int64_t', 'float': 'double', 'bool': 'bool', 'str': 'const char *', 'bytes': 'const uint8_t *, size_t',
            'ints': 'const int64_t *, size_t', 'floats': 'const double *, size_t', 'void': 'void'}.get(kind) or type_name


def public_header(name, manifest, link_flags=()):
    upper = name.upper()
    structs = manifest['structs']
    lines = ['#ifndef %s_AIL_EXPORT_H' % upper, '#define %s_AIL_EXPORT_H' % upper,
             '/* C API of the AIL library "%s", generated by `ail build --lib %s`. Do not edit.' % (name, name),
             '',
             '   Every function returns a status: 0 on success, otherwise one of the %s_ERR_* values.' % upper,
             '   Results come back through the trailing out-parameters and are untouched on failure.',
             '   %s_last_error() gives "Kind: text" for the calling thread\'s most recent failure (""' % name,
             '   after a success); the pointer stays valid until that thread\'s next call into this library.',
             '   An exception raised by the AIL code, an invalid argument (NULL where a pointer is needed) or an',
             '   allocation failure is reported this way; it never terminates or crashes the host process.',
             '',
             '   Types: int -> int64_t, float -> double, bool -> bool.',
             '   str in: const char * (NUL terminated, UTF-8). str out: char ** (malloc\'d, NUL terminated).',
             '   bytes in: pointer + length (any alignment). bytes out: uint8_t ** + size_t * (malloc\'d).',
             '   list[int] / list[float]: const T * + element count in (T aligned); T ** + size_t * out (malloc\'d).',
             '   dataclass of int/float/bool: a C struct of the same fields, passed by const pointer.',
             '   Release every str, bytes and list result with %s_free() exactly once (NULL is fine).' % name,
             '   An empty bytes or list result may be NULL with length 0.',
             '',
             '   Threads: any thread may call at any time; one mutex serializes the calls. There is no',
             '   init or teardown function, no state survives a call, and calls may not be made from a',
             '   signal handler. Link with -lm -lpthread%s when using lib%s.a. */'
             % (' ' + shlex.join(link_flags) if link_flags else '', name),
             '#include <stdbool.h>', '#include <stddef.h>', '#include <stdint.h>', '#ifdef __cplusplus', 'extern "C" {', '#endif',
             '#define %s_API __attribute__((visibility("default")))' % upper, '']
    for label, number, kind in STATUS:
        lines.append('#define %s_%s %d' % (upper, 'OK' if label == 'OK' else 'ERR_' + label, number))
    lines.append('')
    for struct, fields in structs.items():
        lines.append('typedef struct %s_%s {' % (name, struct))
        lines.extend('    %s %s;' % (SCALAR_C[f['kind']], f['name']) for f in fields)
        lines.append('} %s_%s;' % (name, struct))
        lines.append('')
    lines += ['%s_API const char *%s_last_error(void);' % (upper, name), '%s_API void %s_free(void *data);' % (upper, name), '']
    for export in manifest['exports']:
        params, outs, _, _, _, _ = _signature(name, export, structs)
        doc = '%s(%s) -> %s' % (export['name'], ', '.join('%s: %s' % (p['name'], p.get('type') or p['kind']) for p in export['params']),
                                export['result']['kind'])
        lines.append('/* %s */' % doc)
        lines.append('%s_API int %s_%s(%s);' % (upper, name, export['name'], ', '.join(params + outs) or 'void'))
    lines += ['', '#ifdef __cplusplus', '}', '#endif', '#endif', '']
    return '\n'.join(lines).replace('NAME_ERR', upper + '_ERR')


def shim_source(name, manifest, core_header):
    upper = name.upper()
    core = name + '_core'
    structs = manifest['structs']
    out = ['#include <stdint.h>', '#include <stdlib.h>', '#include <stdio.h>', '#include <string.h>',
           '#include <stdbool.h>', '#include <stdalign.h>',
           '#include "%s"' % core_header, '#include "%s.h"' % name,
           '#include <pthread.h>',
           'static pthread_mutex_t %s_lock = PTHREAD_MUTEX_INITIALIZER;' % name,
           'static void %s_acquire(void) { pthread_mutex_lock(&%s_lock); }' % (name, name),
           'static void %s_release(void) { pthread_mutex_unlock(&%s_lock); }' % (name, name),
           'static _Thread_local char %s_error_text[256];' % name,
           'static const char *const %s_kinds[] = {"Error", "ValueError", "ZeroDivisionError", "IndexError", "KeyError", '
           '"EOFError", "OSError", "RuntimeError", "InternalError", "InvalidArgument", "Busy"};' % name,
           'static int %s_fail(int code, const char *text) {' % name,
           '    snprintf(%s_error_text, sizeof %s_error_text, "%%s: %%s", %s_kinds[code > 0 && code <= 10 ? code : 0], text);' % (name, name, name),
           '    return code ? code : %s_ERR_INTERNAL;' % upper, '}',
           'static int %s_ok(void) { %s_error_text[0] = 0; return 0; }' % (name, name),
           '%s_API const char *%s_last_error(void) { return %s_error_text; }' % (upper, name, name),
           '%s_API void %s_free(void *data) { %s_free(data); }' % (upper, name, core), '']
    for export in manifest['exports']:
        params, outs, checks, call, core_out, finish = _signature(name, export, structs)
        fn = export['wrapper']
        body = ['%s_API int %s_%s(%s) {' % (upper, name, export['name'], ', '.join(params + outs) or 'void'),
                '    %s_error error;' % core]
        if core_out:
            body.append('    %s value;' % core_out)
        body += ['    ' + c for c in checks]
        body += ['    %s_acquire();' % name,
                 '    int status = %s_%s(%s);' % (core, fn, ', '.join(call + (['&value'] if core_out else []) + ['&error'])),
                 '    %s_release();' % name,
                 '    if (status) return %s_fail(status, error.message);' % name]
        body += ['    ' + f for f in finish]
        body += ['    return %s_ok();' % name, '}', '']
        out.extend(body)
    return '\n'.join(out).replace('NAME_ERR', upper + '_ERR')


def _tool(cc, flag, fallback):
    try:
        found = subprocess.run([cc, '-print-prog-name=' + flag], capture_output=True, timeout=20).stdout.decode().strip()
    except (OSError, subprocess.SubprocessError):
        found = ''
    return shutil.which(found) or shutil.which(fallback)


def build(source, manifest, name, output, objects=(), link_flags=()):
    """`objects`: the FFI adapter object of `@extern` stubs (built with --c-api-name <name>_core) and
    `link_flags` its libraries (-lz): both go into the .so and the .a, and the flags into <name>.h."""
    if os.name == 'nt':
        raise Unsupported('ail build --lib is supported on Linux and macOS (Windows hosts: use compile-library)')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,41}', name) or name.startswith('ail_'):
        raise Unsupported('library name must be an ASCII identifier (1..42 characters), not ail_*')
    output = Path(output)
    if not output.is_dir():
        raise Unsupported('library output directory does not exist: %s' % output)
    shared_suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    targets = [output / ('lib%s%s' % (name, shared_suffix)), output / ('lib%s.a' % name), output / (name + '.h')]
    for target in targets:
        if target.exists() or target.is_symlink():
            raise Unsupported('output already exists: %s' % target)
    if any(e['name'] in ('free', 'last_error') for e in manifest['exports']):
        raise Unsupported('exported names free and last_error are reserved')
    core = name + '_core'
    cc = compiler()
    with tempfile.TemporaryDirectory(prefix='ail-lib-') as temporary:
        root = Path(temporary)
        report = c_api.build(source, root / 'core', core, [e['wrapper'] for e in manifest['exports']],
                             internal=set(manifest['internal']), pic=True, objects=objects)
        header = public_header(name, manifest, link_flags)
        (root / (name + '.h')).write_text(header, encoding='utf8')
        shim = root / 'shim.c'
        shim.write_text(shim_source(name, manifest, core + '.h'), encoding='utf8')
        shim_object = root / 'shim.o'
        flags = [*FLAGS, '-fPIC', '-fvisibility=hidden', '-std=gnu11', '-Wall']
        result = native_diagnostics.run([cc, *flags, '-I', str(root / 'core'), '-I', str(root), '-c', str(shim), '-o', str(shim_object)],
                                        phase='compile', capture_output=True, timeout=180)
        if result.returncode:
            raise PipelineError('C export shim compile failed: ' + result.stderr.decode(errors='replace')[-4000:])
        core_object = root / 'core' / (core + '.o')
        libraries = ['-l' + lib for lib in report.get('link_libraries', [])] + list(link_flags)
        shared = root / targets[0].name
        link = [cc, '-shared', '-o', str(shared), str(shim_object), str(core_object), *libraries, '-lpthread']
        if sys.platform != 'darwin':
            link[2:2] = ['-Wl,-soname,' + targets[0].name, '-Wl,-z,noexecstack']
        result = native_diagnostics.run(link, phase='link', capture_output=True, timeout=180)
        if result.returncode:
            raise PipelineError('C library link failed: ' + result.stderr.decode(errors='replace')[-4000:])
        archive = root / targets[1].name
        ar = _tool(cc, 'ar', 'ar')
        if not ar:
            raise Unsupported('building lib%s.a needs ar, and none was found next to %s' % (name, cc))
        result = native_diagnostics.run([ar, 'rcs', str(archive), str(shim_object), str(core_object)],
                                        phase='archive', capture_output=True, timeout=180)
        if result.returncode:
            raise PipelineError('C library archive failed: ' + result.stderr.decode(errors='replace')[-4000:])
        written = []
        try:
            for source_path, target in ((shared, targets[0]), (archive, targets[1]), (root / (name + '.h'), targets[2])):
                with target.open('xb') as destination:
                    written.append(target)
                    destination.write(source_path.read_bytes())
                shutil.copymode(source_path, target)
        except Exception:
            for target in written:
                target.unlink()
            raise
    return {'schema': 1, 'name': name, 'files': {t.name: hashlib.sha256(t.read_bytes()).hexdigest() for t in targets},
            'output': str(output), 'exports': [e['name'] for e in manifest['exports']]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--name', required=True)
    parser.add_argument('-o', '--output', type=Path, required=True)
    parser.add_argument('--object', action='append', type=Path, default=[])
    parser.add_argument('--ffi-link', action='append', default=[], help='a link flag the FFI object needs (use --ffi-link=-lz)')
    parser.add_argument('--native-report', help=argparse.SUPPRESS)
    parser.add_argument('--native-debug-dir', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.native_report:
        native_diagnostics.configure(args.native_report, args.native_debug_dir)
    try:
        print(json.dumps(build(args.source.read_text(encoding='utf8'), json.loads(args.manifest.read_text(encoding='utf8')),
                               args.name, args.output, tuple(args.object), tuple(args.ffi_link))))
    except (ValueError, Unsupported, PipelineError, OSError) as error:
        native_diagnostics.failure(error)
        parser.exit(1, str(error) + '\n')
