"""F1: `compile --lib` takes local modules and `@extern` stubs.

A package `geo/` (`__init__.py`, `vec.py`) and an entry `api.py` whose `@export` functions use it, plus one zlib
`crc32` extern, are built into libgeomath.so, libgeomath.a and geomath.h. The same calls are made

* on CPython, importing api.py itself (the reference, ail_ffi's ctypes shim for the extern),
* from Python through ctypes on the .so,
* from a C host linked statically (the flags come from the comment in geomath.h) and with the shared library,
  the static one also built with AddressSanitizer and UBSan, and

every line must equal the CPython line. Also covered: the stub inside an imported module, `@export` outside the
entry file and `link()` of a `.so` path (both refused with file:line and `write instead:`), and that a
single-file library keeps its header.
"""
import ctypes
import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from ail_testenv import ASAN_DETECT_LEAKS, WINDOWS

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')
CC = os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
EXAMPLE = ROOT / 'language_examples' / 'c_export'
sys.path.insert(0, str(ROOT))

SKIP = unittest.skipIf(WINDOWS or CC is None, '`compile --lib` needs a POSIX host and a C compiler')

VEC = '''SCALE = 2


def dot(ax: int, ay: int, bx: int, by: int) -> int:
    return ax * bx + ay * by


def norm2(x: int, y: int) -> int:
    return dot(x, y, x, y)


def scale_all(values: list[int]) -> list[int]:
    out = []
    for v in values:
        out.append(v * SCALE)
    return out
'''

STUB = '''@extern(lib="z", header="zlib.h", symbol="crc32")
def zlib_crc32(crc: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...
'''

API_HEAD = '''from ail_ffi import export, extern, length, c_ulong, c_uint
from geo.vec import dot, norm2, scale_all
'''

API_BODY = '''

@export
def inner(ax: int, ay: int, bx: int, by: int) -> int:
    return dot(ax, ay, bx, by)


@export
def length2(x: int, y: int) -> int:
    return norm2(x, y)


@export
def doubled(values: list[int]) -> list[int]:
    return scale_all(values)
'''

API = API_HEAD + '\n' + STUB + API_BODY + '''

@export
def checksum(data: bytes) -> int:
    return zlib_crc32(0, data)
'''

# the same extern, declared in an imported module and re-exported by a wrapper in the entry
SUMS = 'from ail_ffi import extern, length, c_ulong, c_uint\n\n' + STUB + '''

def crc_of(data: bytes) -> int:
    return zlib_crc32(0, data)
'''
API_VIA_MODULE = '''from ail_ffi import export
from geo.sums import crc_of


@export
def checksum(data: bytes) -> int:
    return crc_of(data)
'''

HOST = r'''
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include "geomath.h"

static int fail(const char *what, int status) {
    fprintf(stderr, "%s failed: %d %s\n", what, status, geomath_last_error());
    return 1;
}

int main(void) {
    int64_t v = 0;
    if (geomath_inner(1, 2, 3, 4, &v)) return fail("inner", 1);
    printf("inner(1, 2, 3, 4) = %" PRId64 "\n", v);
    if (geomath_inner(-5, 6, 7, 8, &v)) return fail("inner", 1);
    printf("inner(-5, 6, 7, 8) = %" PRId64 "\n", v);
    if (geomath_length2(3, 4, &v)) return fail("length2", 1);
    printf("length2(3, 4) = %" PRId64 "\n", v);
    int64_t in[3] = {1, 2, 3};
    int64_t *out = NULL;
    size_t n = 0;
    if (geomath_doubled(in, 3, &out, &n)) return fail("doubled", 1);
    printf("doubled([1, 2, 3]) =");
    for (size_t i = 0; i < n; i++) printf(" %" PRId64, out[i]);
    printf("\n");
    geomath_free(out);
    if (geomath_doubled(NULL, 0, &out, &n)) return fail("doubled", 1);
    printf("doubled([]) =");
    for (size_t i = 0; i < n; i++) printf(" %" PRId64, out[i]);
    printf("\n");
    geomath_free(out);
    const uint8_t text[] = "hello, zlib";
    if (geomath_checksum(text, sizeof text - 1, &v)) return fail("checksum", 1);
    printf("checksum(b'hello, zlib') = %" PRId64 "\n", v);
    if (geomath_checksum(NULL, 0, &v)) return fail("checksum", 1);
    printf("checksum(b'') = %" PRId64 "\n", v);
    return 0;
}
'''


def reference(api):
    """The expected output: the exported Python functions called directly on CPython."""
    return [
        'inner(1, 2, 3, 4) = %d' % api.inner(1, 2, 3, 4),
        'inner(-5, 6, 7, 8) = %d' % api.inner(-5, 6, 7, 8),
        'length2(3, 4) = %d' % api.length2(3, 4),
        'doubled([1, 2, 3]) =' + ''.join(' %d' % v for v in api.doubled([1, 2, 3])),
        'doubled([]) =' + ''.join(' %d' % v for v in api.doubled([])),
        "checksum(b'hello, zlib') = %d" % api.checksum(b'hello, zlib'),
        "checksum(b'') = %d" % api.checksum(b''),
    ]


def write_tree(root, files):
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


def build_lib(root, name='geomath', entry='api.py', extra=()):
    out = Path(root) / 'out'
    out.mkdir(exist_ok=True)
    return subprocess.run([sys.executable, '-B', CLI, 'compile', '--lib', name, entry, '-o', str(out), *extra],
                          cwd=root, capture_output=True, text=True, timeout=900), out


def link_flags(header):
    """What geomath.h tells a static consumer to link with."""
    found = re.search(r'Link with (.*?) when using libgeomath\.a', header)
    return found.group(1).split() if found else []


class Built:
    root = None
    out = None
    expected = None

    @classmethod
    def build(cls):
        if cls.root is None:
            cls.root = Path(tempfile.mkdtemp(prefix='ail-lib-modules-'))
            write_tree(cls.root, {'geo/__init__.py': '"""Small vector helpers."""\n', 'geo/vec.py': VEC, 'api.py': API})
            result, cls.out = build_lib(cls.root)
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
            cls.expected = cls.cpython()
        return cls

    @classmethod
    def cpython(cls):
        sys.path.insert(0, str(cls.root))
        try:
            return reference(importlib.import_module('api'))
        finally:
            sys.path.remove(str(cls.root))
            for name in [n for n in sys.modules if n == 'api' or n == 'geo' or n.startswith('geo.')]:
                del sys.modules[name]


def tearDownModule():
    if Built.root is not None:
        shutil.rmtree(Built.root, ignore_errors=True)


@SKIP
class LibraryWithModulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = Built.build()
        cls.out = cls.built.out
        cls.expected = cls.built.expected

    def test_cpython_reference_is_the_real_zlib(self):
        self.assertIn("checksum(b'hello, zlib') = %d" % zlib.crc32(b'hello, zlib'), self.expected)
        self.assertIn('inner(1, 2, 3, 4) = 11', self.expected)
        self.assertIn('doubled([1, 2, 3]) = 2 4 6', self.expected)

    def test_three_files_and_only_the_public_symbols(self):
        suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        self.assertEqual(sorted(p.name for p in self.out.iterdir()),
                         sorted(['geomath.h', 'libgeomath.a', 'libgeomath' + suffix]))
        if shutil.which('nm') and sys.platform.startswith('linux'):
            symbols = subprocess.run(['nm', '-D', '--defined-only', str(self.out / 'libgeomath.so')],
                                     capture_output=True, text=True).stdout.split()
            self.assertEqual(sorted(s for s in symbols if s.startswith('geomath_')),
                             sorted('geomath_' + n for n in ('last_error', 'free', 'inner', 'length2', 'doubled', 'checksum')))
            self.assertFalse([s for s in symbols if s.startswith(('ail_', 'ffi_', 'geo__')) or 'abi' in s])

    def test_only_entry_functions_are_exported(self):
        header = (self.out / 'geomath.h').read_text(encoding='utf-8')
        self.assertIn('int geomath_inner(int64_t ax, int64_t ay, int64_t bx, int64_t by, int64_t *out);', header)
        self.assertIn('int geomath_checksum(const uint8_t *data, size_t data_len, int64_t *out);', header)
        self.assertNotIn('geomath_dot', header)
        self.assertNotIn('geomath_norm2', header)
        self.assertNotIn('geomath_zlib_crc32', header)

    def test_header_prints_the_link_flags_of_a_static_consumer(self):
        header = (self.out / 'geomath.h').read_text(encoding='utf-8')
        self.assertEqual(link_flags(header), ['-lm', '-lpthread', '-lz'])

    def test_shared_library_records_the_dependency(self):
        if shutil.which('readelf') and sys.platform.startswith('linux'):
            needed = subprocess.run(['readelf', '-d', str(self.out / 'libgeomath.so')], capture_output=True, text=True).stdout
            self.assertRegex(needed, r'NEEDED.*libz\.so')

    def test_ctypes_matches_cpython(self):
        lib = ctypes.CDLL(str(self.out / ('libgeomath.dylib' if sys.platform == 'darwin' else 'libgeomath.so')))
        lib.geomath_last_error.restype = ctypes.c_char_p
        lib.geomath_free.argtypes = [ctypes.c_void_p]
        value = ctypes.c_int64()
        got = []
        for label, args in (('inner(1, 2, 3, 4)', (1, 2, 3, 4)), ('inner(-5, 6, 7, 8)', (-5, 6, 7, 8))):
            self.assertEqual(lib.geomath_inner(*[ctypes.c_int64(a) for a in args], ctypes.byref(value)), 0)
            got.append('%s = %d' % (label, value.value))
        self.assertEqual(lib.geomath_length2(ctypes.c_int64(3), ctypes.c_int64(4), ctypes.byref(value)), 0)
        got.append('length2(3, 4) = %d' % value.value)
        for label, items in (('doubled([1, 2, 3])', [1, 2, 3]), ('doubled([])', [])):
            array = (ctypes.c_int64 * max(len(items), 1))(*items)
            out, count = ctypes.c_void_p(), ctypes.c_size_t()
            self.assertEqual(lib.geomath_doubled(array, ctypes.c_size_t(len(items)), ctypes.byref(out), ctypes.byref(count)), 0)
            result = list((ctypes.c_int64 * count.value).from_address(out.value)) if out.value else []
            lib.geomath_free(out)
            got.append(label + ' =' + ''.join(' %d' % v for v in result))
        for label, data in (("checksum(b'hello, zlib')", b'hello, zlib'), ("checksum(b'')", b'')):
            buffer = ctypes.create_string_buffer(data, max(len(data), 1))
            self.assertEqual(lib.geomath_checksum(buffer, ctypes.c_size_t(len(data)), ctypes.byref(value)), 0)
            got.append('%s = %d' % (label, value.value))
        self.assertEqual(got, self.expected)

    def host(self, directory, archive, flags=(), sanitize=False):
        host = Path(directory) / 'host'
        (Path(directory) / 'host.c').write_text(HOST, encoding='utf-8')
        command = [CC, '-std=gnu11', '-Wall', '-Werror', '-g', '-O1', *(
            ['-fno-omit-frame-pointer', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined'] if sanitize else []),
            str(Path(directory) / 'host.c'), '-I', str(self.out), *archive, *flags, '-o', str(host)]
        return host, subprocess.run(command, capture_output=True, text=True)

    def test_c_host_links_the_static_library_with_the_printed_flags(self):
        with tempfile.TemporaryDirectory(prefix='ail-lib-host-') as temporary:
            flags = link_flags((self.out / 'geomath.h').read_text(encoding='utf-8'))
            host, built = self.host(temporary, [str(self.out / 'libgeomath.a')], flags)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(host)], capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout.splitlines(), self.expected)

    def test_static_library_needs_the_printed_zlib_flag(self):
        with tempfile.TemporaryDirectory(prefix='ail-lib-host-') as temporary:
            _, built = self.host(temporary, [str(self.out / 'libgeomath.a')], ['-lm', '-lpthread'])
            self.assertNotEqual(built.returncode, 0)
            self.assertIn('crc32', built.stderr)

    def test_c_host_links_the_shared_library(self):
        with tempfile.TemporaryDirectory(prefix='ail-lib-host-') as temporary:
            host, built = self.host(temporary, ['-L', str(self.out), '-lgeomath'], ['-lpthread', '-Wl,-rpath,' + str(self.out)])
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(host)], capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout.splitlines(), self.expected)

    def test_c_host_under_asan_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-lib-asan-') as temporary:
            flags = link_flags((self.out / 'geomath.h').read_text(encoding='utf-8'))
            host, built = self.host(temporary, [str(self.out / 'libgeomath.a')], flags, sanitize=True)
            if built.returncode and 'sanitize' in built.stderr:
                self.skipTest('this compiler cannot build with AddressSanitizer: ' + built.stderr[-200:])
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(host)], capture_output=True, timeout=300,
                                 env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1' if ASAN_DETECT_LEAKS.endswith('1') else 'detect_leaks=0',
                                      'UBSAN_OPTIONS': 'halt_on_error=1'})
            self.assertEqual(run.returncode, 0, run.stderr.decode('utf-8', 'replace')[-3000:])
            self.assertEqual(run.stderr.decode('utf-8', 'replace'), '')
            self.assertEqual(run.stdout.decode('utf-8').splitlines(), self.expected)


@SKIP
class LibraryBuildVariantTests(unittest.TestCase):
    def test_stub_in_an_imported_module(self):
        with tempfile.TemporaryDirectory(prefix='ail-lib-sums-') as temporary:
            write_tree(temporary, {'geo/__init__.py': '', 'geo/vec.py': VEC, 'geo/sums.py': SUMS, 'api.py': API_VIA_MODULE})
            result, out = build_lib(temporary)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('-lz', link_flags((out / 'geomath.h').read_text(encoding='utf-8')))
            lib = ctypes.CDLL(str(out / ('libgeomath.dylib' if sys.platform == 'darwin' else 'libgeomath.so')))
            value = ctypes.c_int64()
            data = ctypes.create_string_buffer(b'abc', 3)
            self.assertEqual(lib.geomath_checksum(data, ctypes.c_size_t(3), ctypes.byref(value)), 0)
            self.assertEqual(value.value, zlib.crc32(b'abc'))

    def test_export_outside_the_entry_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-lib-refuse-') as temporary:
            vec = 'from ail_ffi import export\n\n' + VEC.replace('def norm2', '@export\ndef norm2')
            write_tree(temporary, {'geo/__init__.py': '', 'geo/vec.py': vec, 'api.py': API_HEAD + API_BODY})
            result, out = build_lib(temporary)
            text = result.stderr + result.stdout
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('geo/vec.py:', text)
            line = vec.splitlines().index('@export') + 1
            self.assertIn('geo/vec.py:%d:' % line, text)
            self.assertIn('@export on norm2', text)
            self.assertIn('only api.py declares the C API', text)
            self.assertIn('write instead:', text)
            self.assertEqual(list(out.iterdir()), [])

    def test_link_of_a_shared_object_is_refused_for_the_archive(self):
        with tempfile.TemporaryDirectory(prefix='ail-lib-so-') as temporary:
            api = ('from ail_ffi import export, extern, link, length, c_ulong, c_uint\n'
                   'link("vendor/libdemo.so")\n\n'
                   '@extern(header="zlib.h", symbol="crc32")\n'
                   'def zlib_crc32(crc: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...\n\n\n'
                   '@export\ndef checksum(data: bytes) -> int:\n    return zlib_crc32(0, data)\n')
            write_tree(temporary, {'api.py': api})
            result, out = build_lib(temporary)
            text = result.stderr + result.stdout
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('api.py:2:', text)
            self.assertIn("link of the shared library 'vendor/libdemo.so' cannot go into libgeomath.a", text)
            self.assertIn('write instead:', text)
            self.assertEqual(list(out.iterdir()), [])

    def test_link_option_with_a_shared_object_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-lib-so2-') as temporary:
            write_tree(temporary, {'api.py': API_HEAD.split('\n')[0] + '\n\n@export\ndef f(x: int) -> int:\n    return x\n'})
            result, _ = build_lib(temporary, extra=('--link', 'vendor/libdemo.so'))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('cannot go into libgeomath.a', result.stderr + result.stdout)

    def test_single_file_library_keeps_its_header(self):
        with tempfile.TemporaryDirectory(prefix='ail-lib-single-') as temporary:
            out = Path(temporary) / 'out'
            out.mkdir()
            result = subprocess.run([sys.executable, '-B', CLI, 'compile', '--lib', 'geometry',
                                     str(EXAMPLE / 'geometry.py'), '-o', str(out)], capture_output=True, text=True, timeout=900)
            self.assertEqual(result.returncode, 0, result.stderr)
            header = (out / 'geometry.h').read_text(encoding='utf-8')
            self.assertIn('Link with -lm -lpthread when using libgeometry.a. */', header)


if __name__ == '__main__':
    unittest.main()
