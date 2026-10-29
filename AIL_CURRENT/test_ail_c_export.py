"""`@export` and `ail build --lib`: AIL code as a C library for any language.

language_examples/c_export/geometry.py is built into libgeometry.so, libgeometry.a and geometry.h, and the
same calls are made

* on CPython, importing the file itself (the reference),
* from Python through ctypes (the shared library),
* from C (host.c, linked statically, built with AddressSanitizer and UBSan so a result that is not freed,
  a double free or an out-of-bounds read fails the test), including four threads calling at once, and
* from Rust (host.rs, a subset of the calls; skipped when rustc is missing),

and every line of output must match the CPython line. Also covered: the header contents, the exported
symbols, errors as status + geometry_last_error() (no crash), NULL arguments, the packaged `ail build --lib`,
the refusals of the front end (ail_export.lower), the CPython checks of the decorator, and that a program
without @export compiles exactly as before.
"""
import ctypes
import dataclasses
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import typing
import unittest
from pathlib import Path

from ail_testenv import ASAN_DETECT_LEAKS, WINDOWS, rustc_path

ROOT = Path(__file__).resolve().parent
EXAMPLE = ROOT / 'language_examples' / 'c_export'
CLI = str(ROOT / 'ail_chatgpt.py')
CC = os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
RUSTC = rustc_path()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EXAMPLE))

import ail_export                      # noqa: E402
import ail_ffi                         # noqa: E402
import geometry                        # noqa: E402  (the same file the library is built from, run by CPython)

SKIP = unittest.skipIf(WINDOWS or CC is None, '`ail build --lib` needs a POSIX host and a C compiler')

POINT = geometry.Point

# (label, function, arguments, result kind); host.c prints the same labels in the same order
CASES = [
    ('add(2, 3)', 'add', (2, 3), 'int'),
    ('add(-7, 4)', 'add', (-7, 4), 'int'),
    ('scaled(1.5)', 'scaled', (1.5,), 'float'),
    ('divide(7, 2)', 'divide', (7, 2), 'int'),
    ('divide(-7, 2)', 'divide', (-7, 2), 'int'),
    ('divide(7, 0)', 'divide', (7, 0), 'int'),
    ("parse_digit('7')", 'parse_digit', ('7',), 'int'),
    ("parse_digit('x')", 'parse_digit', ('x',), 'int'),
    ("parse_digit('')", 'parse_digit', ('',), 'int'),
    ('negate(True)', 'negate', (True,), 'bool'),
    ('negate(False)', 'negate', (False,), 'bool'),
    ("shout('h\u00e9llo')", 'shout', ('h\u00e9llo',), 'str'),
    ("shout('')", 'shout', ('',), 'str'),
    ("shout('a\U0001f600')", 'shout', ('a\U0001f600',), 'str'),
    ('reverse_bytes(01020300ff)', 'reverse_bytes', (bytes([1, 2, 3, 0, 255]),), 'bytes'),
    ('reverse_bytes()', 'reverse_bytes', (b'',), 'bytes'),
    ('total([1, 2, 3, 4])', 'total', ([1, 2, 3, 4],), 'int'),
    ('total([])', 'total', ([],), 'int'),
    ('squares([1, 2, 3, 4])', 'squares', ([1, 2, 3, 4],), 'ints'),
    ('squares([])', 'squares', ([],), 'ints'),
    ('first_item([1, 2, 3, 4])', 'first_item', ([1, 2, 3, 4],), 'int'),
    ('first_item([])', 'first_item', ([],), 'int'),
    ('mean([1.0, 2.0, 4.5])', 'mean', ([1.0, 2.0, 4.5],), 'float'),
    ('mean([])', 'mean', ([],), 'float'),
    ('halves([1.0, 2.0, 4.5])', 'halves', ([1.0, 2.0, 4.5],), 'floats'),
    ('weight(Point(2, 1.5, True))', 'weight', (POINT(2, 1.5, True),), 'float'),
    ('weight(Point(2, 1.5, False))', 'weight', (POINT(2, 1.5, False),), 'float'),
    ('count_up(3)', 'count_up', (3,), 'none'),
    ('count_up(-1)', 'count_up', (-1,), 'none'),
]


def render(kind, value):
    if kind == 'bool':
        return 'true' if value else 'false'
    if kind == 'float':
        return '%.6g' % value
    if kind == 'bytes':
        return value.hex()
    if kind == 'ints':
        return ''.join(' %d' % v for v in value)
    if kind == 'floats':
        return ''.join(' %.6g' % v for v in value)
    if kind == 'none':
        return 'None'
    return str(value)


def lines(call):
    """The expected output: one `label = result` line per case, errors as `!Kind` (ValueError keeps its message)."""
    out = []
    for label, name, args, kind in CASES:
        try:
            value = call(name, *args)
        except Exception as error:        # CPython's own exception, or the ctypes binding's NativeError of that name
            kind = type(error).__name__
            out.append('%s = !%s' % (label, '%s: %s' % (kind, error) if kind == 'ValueError' else kind))
        else:
            text = render(kind, value)
            # host.c prints list results as "label = a b c" (a space before each element)
            out.append('%s =%s' % (label, text) if kind in ('ints', 'floats') else '%s = %s' % (label, text))
    return out


class Library:
    """Built once for the whole module."""
    directory = None

    @classmethod
    def build(cls):
        if cls.directory is None:
            cls.directory = Path(tempfile.mkdtemp(prefix='ail-c-export-'))
            result = subprocess.run([sys.executable, '-B', CLI, 'compile', '--lib', 'geometry',
                                     str(EXAMPLE / 'geometry.py'), '-o', str(cls.directory)],
                                    capture_output=True, text=True, timeout=600)
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
        return cls.directory


def tearDownModule():
    if Library.directory is not None:
        shutil.rmtree(Library.directory, ignore_errors=True)


class NativeError(Exception):
    pass


_ERROR_CLASSES = {}


def native_error(kind, message):
    if kind not in _ERROR_CLASSES:
        _ERROR_CLASSES[kind] = type(kind, (NativeError,), {})
    return _ERROR_CLASSES[kind](message)


class CtypesBinding:
    """A generic ctypes binding of geometry.h, driven by the Python annotations of the exported functions."""
    def __init__(self, directory):
        self.lib = ctypes.CDLL(str(directory / ('libgeometry.dylib' if sys.platform == 'darwin' else 'libgeometry.so')))
        self.lib.geometry_last_error.restype = ctypes.c_char_p
        self.lib.geometry_free.argtypes = [ctypes.c_void_p]
        self.lib.geometry_free.restype = None
        self.structs = {}

    def struct(self, cls):
        if cls not in self.structs:
            fields = [(f.name, {int: ctypes.c_int64, float: ctypes.c_double, bool: ctypes.c_bool}[f.type])
                      for f in dataclasses.fields(cls)]
            self.structs[cls] = type('geometry_' + cls.__name__, (ctypes.Structure,), {'_fields_': fields})
        return self.structs[cls]

    def __call__(self, name, *args):
        function = getattr(self.lib, 'geometry_' + name)
        hints = typing.get_type_hints(getattr(geometry, name))
        result = hints.pop('return')
        function.restype = ctypes.c_int
        call, keep = [], []
        for (parameter, annotation), value in zip(hints.items(), args):
            if annotation is int:
                call.append(ctypes.c_int64(value))
            elif annotation is float:
                call.append(ctypes.c_double(value))
            elif annotation is bool:
                call.append(ctypes.c_bool(value))
            elif annotation is str:
                call.append(ctypes.c_char_p(value.encode('utf-8')))
            elif annotation is bytes:
                buffer = ctypes.create_string_buffer(value, max(len(value), 1))
                keep.append(buffer)
                call += [ctypes.cast(buffer, ctypes.c_void_p), ctypes.c_size_t(len(value))]
            elif typing.get_origin(annotation) is list:
                element = ctypes.c_int64 if typing.get_args(annotation) == (int,) else ctypes.c_double
                array = (element * max(len(value), 1))(*value)
                keep.append(array)
                call += [ctypes.cast(array, ctypes.c_void_p), ctypes.c_size_t(len(value))]
            else:
                struct = self.struct(annotation)
                record = struct(*[getattr(value, f.name) for f in dataclasses.fields(annotation)])
                keep.append(record)
                call.append(ctypes.byref(record))
        out = ctypes.c_void_p()
        length = ctypes.c_size_t()
        scalar = {int: ctypes.c_int64, float: ctypes.c_double, bool: ctypes.c_bool}.get(result)
        if result is None:
            status = function(*call)
        elif scalar:
            cell = scalar()
            status = function(*call, ctypes.byref(cell))
        elif result is str:
            status = function(*call, ctypes.byref(out))
        else:
            status = function(*call, ctypes.byref(out), ctypes.byref(length))
        if status:
            text = self.lib.geometry_last_error().decode('utf-8')
            kind, _, message = text.partition(': ')
            raise native_error(kind, message)
        if result is None:
            return None
        if scalar:
            return cell.value
        if result is str:
            value = ctypes.string_at(out.value).decode('utf-8')
        else:
            if result is bytes:
                value = ctypes.string_at(out.value, length.value) if out.value else b''
            else:
                element = ctypes.c_int64 if typing.get_args(result) == (int,) else ctypes.c_double
                value = list((element * length.value).from_address(out.value)) if out.value else []
        self.lib.geometry_free(out)
        return value


@SKIP
class ExportLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Library.build()
        cls.expected = lines(lambda name, *args: getattr(geometry, name)(*args))

    def test_three_files_and_only_the_public_symbols(self):
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()),
                         sorted(['geometry.h', 'libgeometry.a', 'libgeometry.dylib' if sys.platform == 'darwin' else 'libgeometry.so']))
        if shutil.which('nm') and sys.platform.startswith('linux'):
            symbols = subprocess.run(['nm', '-D', '--defined-only', str(self.dir / 'libgeometry.so')],
                                     capture_output=True, text=True).stdout.split()
            names = sorted(s for s in symbols if s.startswith('geometry_'))
            self.assertEqual(names, sorted('geometry_' + n for n in (
                'last_error', 'free', 'add', 'scaled', 'divide', 'parse_digit', 'negate', 'shout', 'reverse_bytes',
                'total', 'squares', 'mean', 'halves', 'weight', 'first_item', 'count_up')))
            self.assertFalse([s for s in symbols if s.startswith('ail_') or 'abi' in s])

    def test_header_maps_the_annotations(self):
        header = (self.dir / 'geometry.h').read_text(encoding='utf-8')
        for prototype in (
                'int geometry_add(int64_t a, int64_t b, int64_t *out);',
                'int geometry_scaled(double x, double *out);',
                'int geometry_negate(bool flag, bool *out);',
                'int geometry_shout(const char *text, char **out);',
                'int geometry_reverse_bytes(const uint8_t *data, size_t data_len, uint8_t **out, size_t *out_len);',
                'int geometry_total(const int64_t *values, size_t values_len, int64_t *out);',
                'int geometry_squares(const int64_t *values, size_t values_len, int64_t **out, size_t *out_len);',
                'int geometry_halves(const double *values, size_t values_len, double **out, size_t *out_len);',
                'int geometry_weight(const geometry_Point *p, double *out);',
                'int geometry_count_up(int64_t n);',
                'const char *geometry_last_error(void);', 'void geometry_free(void *data);'):
            self.assertIn(prototype, header)
        self.assertIn('typedef struct geometry_Point {\n    int64_t x;\n    double y;\n    bool visible;\n} geometry_Point;', header)
        self.assertIn('#define GEOMETRY_ERR_ZERO_DIVISION 2', header)
        self.assertNotIn('geometry_init', header)                      # nothing to initialize or tear down
        self.assertNotIn('geometry_shutdown', header)

    def test_ctypes_matches_cpython(self):
        self.assertEqual(lines(CtypesBinding(self.dir)), self.expected)

    def test_c_host_under_asan_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-c-host-') as temporary:
            host = Path(temporary) / 'host'
            command = [CC, '-std=gnu11', '-g', '-O1', '-fno-omit-frame-pointer', '-fsanitize=address,undefined',
                       '-fno-sanitize-recover=undefined', '-Wall', '-Werror', str(EXAMPLE / 'host.c'),
                       '-I', str(self.dir), str(self.dir / 'libgeometry.a'), '-lm', '-lpthread', '-o', str(host)]
            built = subprocess.run(command, capture_output=True, text=True)
            if built.returncode and 'sanitize' in built.stderr:
                self.skipTest('this compiler cannot build with AddressSanitizer: ' + built.stderr[-200:])
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(host)], capture_output=True, timeout=300,
                                 env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1' if ASAN_DETECT_LEAKS.endswith('1') else 'detect_leaks=0',
                                      'UBSAN_OPTIONS': 'halt_on_error=1'})
            output = run.stdout.decode('utf-8').splitlines()
            self.assertEqual(run.returncode, 0, run.stderr.decode('utf-8', 'replace')[-3000:])
            self.assertEqual(run.stderr.decode('utf-8', 'replace'), '')
            self.assertEqual(output[:len(self.expected)], self.expected)
            tail = output[len(self.expected):]
            self.assertEqual(tail[0], 'add(NULL out) = 9')
            self.assertEqual(tail[1], 'shout(NULL) = 9')
            self.assertEqual(tail[2], 'total(NULL, 3) = 9')
            self.assertEqual(tail[3], 'weight(NULL) = 9')
            self.assertEqual(tail[4], 'untouched = 77')                      # results stay unchanged on failure
            self.assertEqual(tail[5], 'last_error = InvalidArgument: NULL struct argument p')
            self.assertEqual(tail[6], "last_error after success = ''")
            self.assertEqual(tail[7], 'threads: 0 failures')

    def test_c_host_links_the_shared_library(self):
        with tempfile.TemporaryDirectory(prefix='ail-c-host-') as temporary:
            host = Path(temporary) / 'host'
            built = subprocess.run([CC, '-std=gnu11', '-Wall', str(EXAMPLE / 'host.c'), '-I', str(self.dir), '-L', str(self.dir),
                                    '-lgeometry', '-lpthread', '-Wl,-rpath,' + str(self.dir), '-o', str(host)],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(host)], capture_output=True, timeout=300)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(run.stdout.decode('utf-8').splitlines()[:len(self.expected)], self.expected)

    @unittest.skipUnless(RUSTC, 'rustc is not installed')
    def test_rust_host_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-rust-host-') as temporary:
            host = Path(temporary) / 'host_rs'
            built = subprocess.run([RUSTC, '--edition', '2021', str(EXAMPLE / 'host.rs'), '-L', str(self.dir),
                                    '-C', 'link-arg=-Wl,-rpath,' + str(self.dir), '-o', str(host)],
                                   capture_output=True, text=True, timeout=600)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(host)], capture_output=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stderr.decode('utf-8', 'replace'))
            got = run.stdout.decode('utf-8').splitlines()
            by_label = {line.partition(' = ')[0].partition(' =')[0]: line for line in self.expected}
            self.assertEqual(len(got), 5)
            for line in got:
                self.assertEqual(line, by_label[line.partition(' = ')[0].partition(' =')[0]])

    def test_last_error_is_per_thread(self):
        binding = CtypesBinding(self.dir)
        import threading
        seen = {}

        def other():
            try:
                binding('divide', 1, 0)
            except NativeError as error:
                seen['kind'] = type(error).__name__
            seen['empty_before'] = None
        binding('add', 1, 2)
        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
        self.assertEqual(seen['kind'], 'ZeroDivisionError')
        self.assertEqual(binding.lib.geometry_last_error(), b'')       # the main thread's last call succeeded

    @unittest.skipUnless((ROOT.parent / 'packaging' / 'ail_lang' / 'cli.py').is_file(), 'the public tree has no packaging/')
    def test_ail_build_lib_through_the_packaged_command(self):
        sys.path.insert(0, str(ROOT.parent / 'packaging'))
        from ail_lang import cli
        with tempfile.TemporaryDirectory(prefix='ail-cli-lib-') as temporary:
            sdk = Path(temporary) / 'sdk'
            shutil.copytree(ROOT, sdk, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            old = cli.SDK
            cli.SDK = sdk
            try:
                out = Path(temporary) / 'out'
                out.mkdir()
                code = cli.main(['build', '--lib', 'geometry', str(EXAMPLE / 'geometry.py'), '-o', str(out)])
            finally:
                cli.SDK = old
            self.assertEqual(code, 0)
            self.assertTrue((out / 'libgeometry.a').is_file() and (out / 'geometry.h').is_file())


@SKIP
class ExportBuildEdgeTests(unittest.TestCase):
    def build(self, text, name='edge', expect=0):
        with tempfile.TemporaryDirectory(prefix='ail-export-edge-') as temporary:
            source = Path(temporary) / 'edge.py'
            source.write_text(text, encoding='utf-8')
            out = Path(temporary) / 'out'
            out.mkdir()
            result = subprocess.run([sys.executable, '-B', CLI, 'compile', '--lib', name, str(source), '-o', str(out)],
                                    capture_output=True, text=True, timeout=600)
            if expect == 0:
                self.assertEqual(result.returncode, 0, result.stderr)
                return result, sorted(p.name for p in out.iterdir())
            self.assertNotEqual(result.returncode, 0)
            return result, []

    def test_refusals_name_the_problem(self):
        header = 'from ail_ffi import export\nfrom dataclasses import dataclass\n'
        cases = [
            (header + '@export\ndef f(x: list[str]) -> int:\n    return 1\n', 'unsupported type list[str]'),
            (header + '@export\ndef f(x) -> int:\n    return 1\n', 'needs a type annotation'),
            (header + '@export\ndef f(x: int):\n    return 1\n', 'annotate the result'),
            (header + '@export\ndef f(x: int = 3) -> int:\n    return x\n', 'without defaults'),
            (header + '@dataclass\nclass P:\n    x: int\n\n@export\ndef f(x: int) -> P:\n    return P(x)\n', 'cannot be returned'),
            (header + '@dataclass\nclass P:\n    x: str\n\n@export\ndef f(p: P) -> int:\n    return 1\n', 'fields are'),
            (header + 'def f(x: int) -> int:\n    return x\n', 'no @export function'),
            (header + '@export\ndef free(x: int) -> int:\n    return x\n', 'reserved'),
            (header + '@export\ndef f(x: int) -> int:\n    return x\n\ndef ailx_f() -> int:\n    return 1\n', 'reserved for the generated'),
            ('from ail_ffi import export, extern\n@export\ndef f(x: int) -> int:\n    return x\n', 'not extern'),
        ]
        for text, message in cases:
            with self.subTest(message=message):
                result, _ = self.build(text, expect=1)
                self.assertIn(message, result.stderr + result.stdout)

    def test_name_and_existing_outputs_are_refused(self):
        text = 'from ail_ffi import export\n@export\ndef f(x: int) -> int:\n    return x\n'
        result, _ = self.build(text, name='ail_bad', expect=1)
        self.assertIn('ail_*', result.stderr + result.stdout)
        with tempfile.TemporaryDirectory(prefix='ail-export-twice-') as temporary:
            source = Path(temporary) / 'edge.py'
            source.write_text(text, encoding='utf-8')
            command = [sys.executable, '-B', CLI, 'compile', '--lib', 'edge', str(source), '-o', temporary]
            self.assertEqual(subprocess.run(command, capture_output=True, timeout=600).returncode, 0)
            again = subprocess.run(command, capture_output=True, text=True, timeout=600)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn('already exists', again.stderr + again.stdout)

    def test_exception_inside_helper_and_all_scalar_kinds_in_one_library(self):
        text = ('from ail_ffi import export\n'
                'def check(x: int) -> int:\n    if x > 10:\n        raise KeyError("too big")\n    return x\n'
                '@export\ndef f(x: int, y: float, b: bool, s: str) -> float:\n    return check(x) + y + (1.0 if b else 0.0) + len(s)\n')
        with tempfile.TemporaryDirectory(prefix='ail-export-kinds-') as temporary:
            source = Path(temporary) / 'k.py'
            source.write_text(text, encoding='utf-8')
            self.assertEqual(subprocess.run([sys.executable, '-B', CLI, 'compile', '--lib', 'kinds', str(source), '-o', temporary],
                                            capture_output=True, timeout=600).returncode, 0)
            lib = ctypes.CDLL(str(Path(temporary) / ('libkinds.dylib' if sys.platform == 'darwin' else 'libkinds.so')))
            lib.kinds_last_error.restype = ctypes.c_char_p
            out = ctypes.c_double()
            call = lambda x: lib.kinds_f(ctypes.c_int64(x), ctypes.c_double(0.5), ctypes.c_bool(True), b'ab', ctypes.byref(out))
            self.assertEqual(call(3), 0)
            self.assertEqual(out.value, 3 + 0.5 + 1 + 2)
            self.assertEqual(call(11), 4)
            self.assertTrue(lib.kinds_last_error().startswith(b'KeyError'))


class DecoratorTests(unittest.TestCase):
    """The CPython side of @export: it checks the annotations and changes nothing else."""
    def test_returns_the_function_unchanged_and_registers_it(self):
        self.assertIs(geometry.add.__ail_export__, True)
        self.assertEqual(geometry.add(2, 3), 5)
        self.assertIn(geometry.add, ail_ffi.exports())
        self.assertEqual(geometry.weight(POINT(3, 2.0, True)), 6.0)

    def test_bad_annotations_are_a_type_error_on_cpython_too(self):
        def make(source):
            namespace = {'export': ail_ffi.export, 'dataclass': dataclasses.dataclass}
            exec(source, namespace)
        for source in ('@export\ndef f(x) -> int:\n    return 1\n',
                       '@export\ndef f(x: int):\n    return 1\n',
                       '@export\ndef f(x: list[str]) -> int:\n    return 1\n',
                       '@export\ndef f(x: int = 1) -> int:\n    return 1\n',
                       '@dataclass\nclass P:\n    x: int\n@export\ndef f(x: int) -> P:\n    return P(x)\n',
                       '@dataclass\nclass P:\n    x: str\n@export\ndef f(p: P) -> int:\n    return 1\n'):
            with self.subTest(source=source), self.assertRaises(TypeError):
                make(source)
        make('@export()\ndef g(x: int) -> None:\n    pass\n')       # the call form is the same decorator

    def test_front_end_strips_cpython_only_code_and_keeps_helpers_private(self):
        text, manifest = ail_export.lower((EXAMPLE / 'geometry.py').read_text(encoding='utf-8'))
        self.assertNotIn('ail_ffi', text)
        self.assertNotIn('dataclass', text)
        self.assertNotIn('__main__', text)
        self.assertIn('def ailx_weight(a0_x: int, a0_y: float, a0_visible: int)', text)
        self.assertIn('Point(a0_x, a0_y, a0_visible != 0)', text)
        self.assertEqual([e['name'] for e in manifest['exports']][:3], ['add', 'scaled', 'divide'])
        self.assertIn('helper_square', manifest['internal'])
        self.assertEqual(manifest['structs']['Point'], [{'name': 'x', 'kind': 'int'}, {'name': 'y', 'kind': 'float'},
                                                         {'name': 'visible', 'kind': 'bool'}])


@SKIP
class UnchangedWithoutExportTests(unittest.TestCase):
    """A program that does not use @export is compiled exactly as before: same C, same library."""
    PLAIN = 'def fib(n: int) -> int:\n    a = 0\n    b = 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\n'

    def test_compile_library_object_is_independent_of_the_export_machinery(self):
        with tempfile.TemporaryDirectory(prefix='ail-plain-lib-') as temporary:
            source = Path(temporary) / 'plain.py'
            source.write_text(self.PLAIN, encoding='utf-8')
            out = Path(temporary) / 'out'
            result = subprocess.run([sys.executable, '-B', CLI, 'compile-library', str(source), '--name', 'plain', '-o', str(out)],
                                    capture_output=True, text=True, timeout=600)
            self.assertEqual(result.returncode, 0, result.stderr)
            header = (out / 'plain.h').read_text(encoding='utf-8')
            self.assertIn('int plain_fib(int64_t arg0, int64_t *out, plain_error *error);', header)
            self.assertNotIn('last_error', header)
            self.assertEqual(sorted(p.name for p in out.iterdir()), ['library.json', 'plain.h', 'plain.o'])

    def test_program_without_export_builds_and_runs_as_before(self):
        with tempfile.TemporaryDirectory(prefix='ail-plain-exe-') as temporary:
            source = Path(temporary) / 'plain.py'
            source.write_text(self.PLAIN + 'print(fib(30))\n', encoding='utf-8')
            exe = Path(temporary) / 'plain'
            result = subprocess.run([sys.executable, '-B', CLI, 'compile', str(source), '-o', str(exe)],
                                    capture_output=True, text=True, timeout=600)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(subprocess.run([str(exe)], capture_output=True, text=True).stdout, '832040\n')

    def test_lib_option_refuses_a_file_without_export(self):
        with tempfile.TemporaryDirectory(prefix='ail-plain-lib2-') as temporary:
            source = Path(temporary) / 'plain.py'
            source.write_text(self.PLAIN, encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', CLI, 'compile', '--lib', 'plain', str(source), '-o', temporary],
                                    capture_output=True, text=True, timeout=600)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('no @export function', result.stderr + result.stdout)


if __name__ == '__main__':
    unittest.main()
