"""GPU stage G1 (docs/design/GPU.md): the `# ail: gpu` marker, the eligibility proof, the kernel IR and its CPU emulation.

No Vulkan and no GPU here.  A marked loop of GPU.md 1.1 is lowered to a kernel, and the kernel to a C function that runs
on the CPU (the "Semantics without Vulkan" of 5.1): it computes into a buffer, sets a flag instead of raising, and the
glue either commits the buffer (flag 0) or throws it away and runs the original loop (CPU replay).  So the rule under
test is the one of GPU.md section 0: the program prints what the same build prints with `AIL_GPU=0`, which is what
CPython prints (or the CPU build's documented loud stop where the typed path has no big integers).

Layers:

* `Runtime`    -- the emulation helpers (gpu.RUNTIME) built alone and driven through ctypes against Python's own
                  arithmetic: int64 overflow, floor division, int(float) range, the float guards, bounds, aliasing.
* `KernelIR`   -- the lowering of loop bodies to kernel IR, and the C text it makes.
* `Markers`    -- which statement a `# ail: gpu` comment marks.
* `Eligible`   -- whole programs (typed path, `compile --gpu`): stdout and exit code equal CPython's, equal the same
                  binary with AIL_GPU=0 and equal the build without --gpu; the trace shows which launches ran on the
                  kernel and which were replayed (and why).
* `Integers`   -- values near the int64 limits: replay, then the CPU build's own behaviour; the exact general path
                  against CPython.
* `General`    -- the general path never offloads: same output, and the build says so.
* `Refusals`   -- every refusal by name with file:line and its `write instead:` hint.
* `Unchanged`  -- programs without a marker (or without --gpu) generate byte-identical C.
"""
import ast
import ctypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

CLI = ROOT / 'ail_chatgpt.py'
CC = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
INT64_MAX, INT64_MIN = (1 << 63) - 1, -(1 << 63)


def run_python(path, stdin=''):
    r = subprocess.run([sys.executable, '-B', str(path)], input=stdin, capture_output=True, text=True, timeout=120)
    return r.stdout, r.returncode


def trace_lines(stderr):
    return [line for line in stderr.splitlines() if line.startswith('gpu: ')]


class Build:
    """One `ail_chatgpt.py compile` of one program text."""

    def __init__(self, directory, name, text, gpu=True, env=None, typed_only=True):
        self.dir = Path(directory)
        self.src = self.dir / (name + '.py')
        self.src.write_text(text.lstrip('\n'), encoding='utf-8')
        self.exe = self.dir / (name + '.exe')
        self.debug = self.dir / (name + '.dbg')
        environ = dict(os.environ, AIL_NO_CACHE='1')
        for key in ('AIL_GPU', 'AIL_GPU_TRACE', 'AIL_GPU_BUILD', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL'):
            environ.pop(key, None)
        if typed_only:
            environ['AIL_NO_GENERAL'] = '1'
        environ.update(env or {})
        cmd = [sys.executable, '-B', str(CLI), 'compile', str(self.src), '-o', str(self.exe), '--no-cache',
               '--debug-dir', str(self.debug)]
        if gpu:
            cmd.append('--gpu')
        r = subprocess.run(cmd, capture_output=True, text=True, env=environ, timeout=600)
        self.returncode, self.stdout, self.stderr = r.returncode, r.stdout, r.stderr

    @property
    def c(self):
        return (self.debug / 'program.c').read_text(encoding='utf-8')

    def run(self, stdin='', **env):
        environ = dict(os.environ)
        for key in ('AIL_GPU', 'AIL_GPU_TRACE'):
            environ.pop(key, None)
        environ.update(env)
        r = subprocess.run([str(self.exe)], input=stdin, capture_output=True, text=True, env=environ, timeout=120)
        return r.stdout, r.returncode, r.stderr


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu1-')
        cls.dir = Path(cls._tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def build(self, name, text, **kw):
        b = Build(self.dir, name, text, **kw)
        self.assertEqual(b.returncode, 0, b.stderr + b.stdout)
        return b

    def expect(self, text, stdin=''):
        path = self.dir / ('cpython_%d.py' % abs(hash(text)))
        path.write_text(text.lstrip('\n'), encoding='utf-8')
        return run_python(path, stdin)


# ---------------------------------------------------------------------------------------------------- the helpers
class Runtime(Base):
    """gpu.RUNTIME alone, as a shared library, against Python's arithmetic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import gpu
        c = cls.dir / 'rt.c'
        c.write_text('#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n' + gpu.RUNTIME + r'''
#define W2(name, T) int64_t w_##name(int64_t a, int64_t b, unsigned *f) { return gk_##name(a, b, f); }
W2(add, int64_t) W2(sub, int64_t) W2(mul, int64_t) W2(floordiv, int64_t) W2(mod, int64_t)
int64_t w_neg(int64_t a, unsigned *f) { return gk_neg(a, f); }
int64_t w_abs(int64_t a, unsigned *f) { return gk_abs(a, f); }
double w_chk(double a, unsigned *f) { return gk_chk(a, f); }
double w_fadd(double a, double b, unsigned *f) { return gk_fadd(a, b, f); }
double w_fsub(double a, double b, unsigned *f) { return gk_fsub(a, b, f); }
double w_fmul(double a, double b, unsigned *f) { return gk_fmul(a, b, f); }
int64_t w_f2i(double a, unsigned *f) { return gk_f2i(a, f); }
int64_t w_floor(double a, unsigned *f) { return gk_floor(a, f); }
int64_t w_ceil(double a, unsigned *f) { return gk_ceil(a, f); }
double w_ffloor(double a, unsigned *f) { return gk_ffloor(a, f); }
double w_i2fx(int64_t a, unsigned *f) { return gk_i2fx(a, f); }
double w_ldf(const double *p, int64_t n, int64_t i, unsigned *f) { return gk_ldf(p, n, i, f); }
int64_t w_ldi(const int64_t *p, int64_t n, int64_t i, unsigned *f) { return gk_ldi(p, n, i, f); }
int w_disjoint(const void *a, int64_t an, const void *b, int64_t bn, int w) { return gk_disjoint(a, an, b, bn, w); }
''', encoding='utf-8')
        so = cls.dir / 'rt.so'
        r = subprocess.run([CC, '-O2', '-ffp-contract=off', '-shared', '-fPIC', '-o', str(so), str(c), '-lm'],
                           capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(r.stderr)
        cls.lib = ctypes.CDLL(str(so))
        i64, dbl, uptr = ctypes.c_int64, ctypes.c_double, ctypes.POINTER(ctypes.c_uint)
        for name in ('add', 'sub', 'mul', 'floordiv', 'mod'):
            f = getattr(cls.lib, 'w_' + name)
            f.restype, f.argtypes = i64, [i64, i64, uptr]
        for name in ('neg', 'abs'):
            f = getattr(cls.lib, 'w_' + name)
            f.restype, f.argtypes = i64, [i64, uptr]
        cls.lib.w_chk.restype, cls.lib.w_chk.argtypes = dbl, [dbl, uptr]
        for name in ('fadd', 'fsub', 'fmul'):
            f = getattr(cls.lib, 'w_' + name)
            f.restype, f.argtypes = dbl, [dbl, dbl, uptr]
        for name in ('f2i', 'floor', 'ceil'):
            f = getattr(cls.lib, 'w_' + name)
            f.restype, f.argtypes = i64, [dbl, uptr]
        cls.lib.w_ffloor.restype, cls.lib.w_ffloor.argtypes = dbl, [dbl, uptr]
        cls.lib.w_i2fx.restype, cls.lib.w_i2fx.argtypes = dbl, [i64, uptr]
        cls.lib.w_ldf.restype, cls.lib.w_ldf.argtypes = dbl, [ctypes.POINTER(dbl), i64, i64, uptr]
        cls.lib.w_ldi.restype, cls.lib.w_ldi.argtypes = i64, [ctypes.POINTER(i64), i64, i64, uptr]
        cls.lib.w_disjoint.restype = ctypes.c_int
        cls.lib.w_disjoint.argtypes = [ctypes.c_void_p, i64, ctypes.c_void_p, i64, ctypes.c_int]
        cls.GK = dict(INDEX=1, ZERODIV=2, OVERFLOW=4, DENORM=8, NAN=16, RANGE=32)

    def call(self, name, *args):
        flag = ctypes.c_uint(0)
        value = getattr(self.lib, 'w_' + name)(*args, ctypes.byref(flag))
        return value, flag.value

    EDGE = [0, 1, -1, 2, -2, 3, -3, 7, -7, 10, 2 ** 31, -2 ** 31, 2 ** 32, 3037000499, 3037000500, -3037000500,
            INT64_MAX, INT64_MAX - 1, INT64_MIN, INT64_MIN + 1, 2 ** 62, -2 ** 62, 2 ** 53, 2 ** 53 + 1]

    def test_int_arithmetic_flags_exactly_when_python_leaves_int64(self):
        for name, op in (('add', lambda a, b: a + b), ('sub', lambda a, b: a - b), ('mul', lambda a, b: a * b)):
            for a in self.EDGE:
                for b in self.EDGE:
                    got, flag = self.call(name, a, b)
                    want = op(a, b)
                    if INT64_MIN <= want <= INT64_MAX:
                        self.assertEqual((got, flag), (want, 0), (name, a, b))
                    else:
                        self.assertEqual(flag, self.GK['OVERFLOW'], (name, a, b))

    def test_floor_division_and_modulo_follow_the_sign_of_the_divisor(self):
        for a in self.EDGE:
            for b in self.EDGE:
                for name, op in (('floordiv', lambda x, y: x // y), ('mod', lambda x, y: x % y)):
                    got, flag = self.call(name, a, b)
                    if b == 0:
                        self.assertEqual(flag, self.GK['ZERODIV'], (name, a, b))
                        continue
                    want = op(a, b)
                    if INT64_MIN <= want <= INT64_MAX:
                        self.assertEqual((got, flag), (want, 0), (name, a, b))
                    else:
                        self.assertEqual(flag, self.GK['OVERFLOW'], (name, a, b))      # INT64_MIN // -1

    def test_negation_and_abs_of_int64_min(self):
        self.assertEqual(self.call('neg', INT64_MIN)[1], self.GK['OVERFLOW'])
        self.assertEqual(self.call('abs', INT64_MIN)[1], self.GK['OVERFLOW'])
        self.assertEqual(self.call('neg', INT64_MAX), (-INT64_MAX, 0))
        self.assertEqual(self.call('abs', -INT64_MAX), (INT64_MAX, 0))
        self.assertEqual(self.call('neg', 0), (0, 0))

    def test_float_to_int_conversions_stop_at_the_int64_range(self):
        import math
        inf, nan = float('inf'), float('nan')
        for x in (0.0, -0.0, 0.5, -0.5, 1.9, -1.9, 2.0, 1e15, -1e15, 9.2e18, -9.2e18, 2.0 ** 63 - 1024.0,
                  -(2.0 ** 63), 2.0 ** 63, -(2.0 ** 63) - 2048.0, 1e19, -1e19, inf, -inf, nan):
            for name, fn in (('f2i', math.trunc), ('floor', math.floor), ('ceil', math.ceil)):
                got, flag = self.call(name, x)
                try:
                    want = fn(x)
                except (ValueError, OverflowError):
                    want = None
                if want is not None and INT64_MIN <= want <= INT64_MAX:
                    self.assertEqual((got, flag), (want, 0), (name, x))
                else:
                    self.assertEqual(flag, self.GK['RANGE'], (name, x))

    def test_float_floor_by_one_is_python_floor_division(self):
        inf, nan = float('inf'), float('nan')
        for x in (0.0, -0.0, 0.3, -0.3, 2.5, -2.5, 1e300, -1e300, 4503599627370497.5, 5e-324 * 0, 1.0, -1.0):
            got, flag = self.call('ffloor', x)
            want = x // 1
            self.assertEqual(flag, 0)
            self.assertEqual(repr(got), repr(want), x)           # -0.0 stays -0.0
        for x in (inf, -inf, nan):
            self.assertEqual(self.call('ffloor', x)[1], self.GK['RANGE'])

    def test_float_guards(self):
        inf, nan = float('inf'), float('nan')
        for x in (0.0, -0.0, 1.0, -1.5, 1e-300, 2.0 ** -1000, 1e308, inf, -inf):
            got, flag = self.call('chk', x)
            self.assertEqual(flag, 0, x)
            self.assertEqual(repr(got), repr(x))
        self.assertEqual(self.call('chk', nan)[1], self.GK['NAN'])
        for x in (5e-324, 1e-310, 2.2250738585072014e-308, 2.0 ** -1001):
            self.assertEqual(self.call('chk', x)[1], self.GK['DENORM'], x)
            self.assertEqual(self.call('chk', -x)[1], self.GK['DENORM'], -x)

    def test_float_ops_flag_nan_made_from_numbers_and_tiny_results(self):
        inf = float('inf')
        self.assertEqual(self.call('fadd', inf, -inf)[1], self.GK['NAN'])
        self.assertEqual(self.call('fsub', inf, inf)[1], self.GK['NAN'])
        self.assertEqual(self.call('fmul', inf, 0.0)[1], self.GK['NAN'])
        self.assertEqual(self.call('fadd', inf, 1.0), (inf, 0))
        self.assertEqual(self.call('fmul', inf, -2.0), (-inf, 0))
        self.assertEqual(self.call('fadd', 0.1, 0.2), (0.1 + 0.2, 0))
        self.assertEqual(repr(self.call('fmul', -0.0, 1.0)[0]), '-0.0')
        self.assertEqual(self.call('fmul', 1e-160, 1e-160)[1], self.GK['DENORM'])      # 1e-320 is subnormal
        self.assertEqual(self.call('fmul', 1e-200, 1e-200)[1], self.GK['DENORM'])      # underflows to 0
        self.assertEqual(self.call('fmul', 1e-100, 1e-100), (1e-200, 0))
        self.assertEqual(self.call('fsub', 1.0000000000000002, 1.0), (2.220446049250313e-16, 0))
        self.assertEqual(self.call('fsub', 2.2250738585072014e-308, 2.225073858507201e-308)[1], self.GK['DENORM'])

    def test_mixed_int_float_comparison_is_exact_only_below_two_to_the_53(self):
        for i in (0, 1, -1, 2 ** 53, -2 ** 53, 12345):
            self.assertEqual(self.call('i2fx', i), (float(i), 0))
        for i in (2 ** 53 + 1, -2 ** 53 - 1, INT64_MAX, INT64_MIN):
            self.assertEqual(self.call('i2fx', i)[1], self.GK['RANGE'])

    def test_loads_are_bounds_checked_and_normalise_negative_indexes(self):
        data = (ctypes.c_double * 3)(1.5, -0.0, 3.5)
        ints = (ctypes.c_int64 * 3)(10, 20, 30)
        for i, want in ((0, 1.5), (2, 3.5), (-1, 3.5), (-3, 1.5)):
            self.assertEqual(self.call('ldf', data, 3, i), (want, 0))
        self.assertEqual(repr(self.call('ldf', data, 3, 1)[0]), '-0.0')
        for i in (3, -4, INT64_MAX, INT64_MIN):
            self.assertEqual(self.call('ldf', data, 3, i)[1], self.GK['INDEX'], i)
            self.assertEqual(self.call('ldi', ints, 3, i)[1], self.GK['INDEX'], i)
        self.assertEqual(self.call('ldi', ints, 3, -2), (20, 0))
        self.assertEqual(self.call('ldf', data, 0, 0)[1], self.GK['INDEX'])               # an empty list
        nan = (ctypes.c_double * 1)(float('nan'))
        self.assertEqual(self.call('ldf', nan, 1, 0)[1], self.GK['NAN'])
        tiny = (ctypes.c_double * 1)(5e-324)
        self.assertEqual(self.call('ldf', tiny, 1, 0)[1], self.GK['DENORM'])

    def test_overlap_of_two_lists(self):
        buf = (ctypes.c_double * 8)()
        addr = ctypes.addressof(buf)
        d = self.lib.w_disjoint
        self.assertEqual(d(addr, 4, addr + 32, 4, 8), 1)          # side by side
        self.assertEqual(d(addr, 4, addr + 24, 4, 8), 0)          # one element shared
        self.assertEqual(d(addr, 4, addr, 4, 8), 0)               # the same list
        self.assertEqual(d(addr + 32, 4, addr, 4, 8), 1)
        self.assertEqual(d(addr, 0, addr, 4, 8), 1)               # an empty list overlaps nothing
        self.assertEqual(d(addr, 8, addr + 8, 1, 8), 0)


# ---------------------------------------------------------------------------------------------------- the markers
class Markers(unittest.TestCase):
    def sites(self, text):
        import gpu
        tree = ast.parse(text)
        marks = gpu.marker_lines(text)
        return {line: (n.lineno, type(n).__name__) for line, n in gpu._target_of(marks, text.splitlines(),
                                                                                  gpu._statements(tree)).items() if n}

    def test_a_comment_on_the_line_before_marks_the_next_statement(self):
        text = 'def f(a):\n    out = [0.0]\n    # ail: gpu\n\n    # more\n    for i in range(3):\n        out[i] = 1\n'
        self.assertEqual(self.sites(text), {3: (6, 'For')})

    def test_a_comment_after_code_marks_the_statement_it_ends(self):
        text = 'def f(a):\n    ys = [\n        x for x in a\n    ]  # ail: gpu\n    for i in range(3):  # ail: gpu\n        pass\n'
        self.assertEqual(self.sites(text), {4: (2, 'Assign'), 5: (5, 'For')})

    def test_other_comments_are_not_markers(self):
        import gpu
        text = '# ail: cpu\n# ail: gpu now\nx = 1  # ail gpu\ny = "# ail: gpu"\nz = 1  # ail: gpu\n'
        self.assertEqual(list(gpu.marker_lines(text)), [5])
        self.assertEqual(list(gpu.marker_lines('x = 1  #AIL:GPU\n')), [1])

    def test_spacing_inside_the_comment_is_free(self):
        import gpu
        self.assertEqual(list(gpu.marker_lines('x = 1  #ail:gpu\ny = 2  #   ail :  gpu  \n')), [1, 2])


# ---------------------------------------------------------------------------------------------------- kernel IR
def fake_oracle(types):
    """The typed half's answers, by name: 'i'/'f' scalars, ('list', 'i'/'f') lists."""
    def oracle(what, name, node):
        kind = types[name]
        if what == 'list':
            return kind[1] if isinstance(kind, tuple) else 'bad'
        return kind if not isinstance(kind, tuple) else 'bad'
    return oracle


def lower(source, types, which=0):
    import gpu
    tree = ast.parse(source)
    sites = gpu.analyze(tree, source)
    for k, s in enumerate(sites):
        s['k'] = k
        s['bounds'] = ('lo', 'hi')
    site = sites[which]
    b = gpu.Builder(site, gpu._funcs_of(tree), fake_oracle(types))
    return b.build_for() if site['kind'] == 'for' else b.build_comp()


class KernelIR(unittest.TestCase):
    LISTS = {'a': ('list', 'f'), 'b': ('list', 'f'), 'xs': ('list', 'i'), 'k': 'f', 'c': 'i'}

    def test_element_wise_float_loop(self):
        k = lower('def f(a, b, k):\n    out = [0.0] * 3\n    # ail: gpu\n    for i in range(3):\n        out[i] = a[i] * b[i] + k\n',
                  self.LISTS)
        self.assertEqual(k.res_type, 'f')
        self.assertEqual(k.lists, {'a': 'f', 'b': 'f'})
        self.assertEqual(k.scalars, {'k': 'f'})
        self.assertIn('(bin f add (bin f mul (ld f a k_i) (ld f b k_i)) s_k)', k.dump())

    def test_int_arithmetic_and_conversions_get_their_types(self):
        k = lower('def f(xs, a):\n    ys = [x // 2 + x % 3 for x in xs]  # ail: gpu\n', self.LISTS)
        self.assertEqual((k.res_type, k.lists), ('i', {'xs': 'i'}))
        k = lower('def f(xs, a):\n    ys = [float(x) * 0.5 for x in xs]  # ail: gpu\n', self.LISTS)
        self.assertEqual(k.res_type, 'f')
        k = lower('def f(a):\n    ys = [int(x) for x in a]  # ail: gpu\n', self.LISTS)
        self.assertEqual(k.res_type, 'i')

    def test_locals_branches_and_inner_loops(self):
        src = ('def f(a, w):\n    out = [0.0] * 3\n    # ail: gpu\n    for i in range(3):\n        acc = 0.0\n'
               '        for j in range(len(w)):\n            if w[j] > 0.0:\n                acc += a[i] * w[j]\n'
               '            else:\n                acc -= 1.0\n        out[i] = acc\n')
        k = lower(src, {'a': ('list', 'f'), 'w': ('list', 'f')})
        text = k.dump()
        self.assertIn('for k_j', text)
        self.assertIn('if ', text)
        self.assertEqual(k.locals['k_acc'], 'f')

    def test_calls_are_inlined(self):
        src = ('def twice(x: float) -> float:\n    y = x * 2.0\n    return y + 1.0\n\n'
               'def f(a):\n    ys = [twice(x) for x in a]  # ail: gpu\n')
        k = lower(src, self.LISTS, 0)
        self.assertIn('{', k.dump())
        self.assertEqual(k.res_type, 'f')

    def test_a_bool_is_an_int_in_arithmetic_and_is_stored_as_zero_or_one(self):
        k = lower('def f(xs):\n    ys = [(x > 1) + 2 for x in xs]  # ail: gpu\n', self.LISTS)
        self.assertEqual(k.res_type, 'i')
        k = lower('def f(xs):\n    ys = [x > 1 for x in xs]  # ail: gpu\n', self.LISTS)
        self.assertEqual(k.res_type, 'i')

    def test_the_emulation_is_valid_c(self):
        import gpu
        src = ('def twice(x: float) -> float:\n    return x * 2.0\n\n'
               'def f(a, xs, k, c):\n    out = [0.0] * 3\n    # ail: gpu\n    for i in range(3):\n'
               '        t = 0.0\n        for j in range(c):\n            t += a[j] if a[j] > k else -a[j]\n'
               '        u = min(t, 3.0) + max(t, k) + abs(t) + twice(k) + float(xs[i] % 5) + math_floor(t)\n'
               '        out[i] = u if (u > 1.0 and not t < 0.0) or c else 0.0\n')
        src = src.replace('math_floor(t)', 'int(t // 1)')
        k = lower(src, self.LISTS)
        text = gpu.RUNTIME + gpu.emit_c(k, 'ail_gk0')
        c = Path(tempfile.mkdtemp(prefix='ail-gk-')) / 'k.c'
        c.write_text('#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n' + text, encoding='utf-8')
        r = subprocess.run([CC, '-O2', '-c', '-o', str(c.with_suffix('.o')), str(c)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        shutil.rmtree(c.parent, ignore_errors=True)



# ---------------------------------------------------------------------------------------------------- programs
FLOAT_PROGRAM = r'''
def twice(x: float) -> float:
    return x * 2.0

def fmap(a: list[float], b: list[float], k: float) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        t = a[i] * b[i]
        out[i] = t + k if t > 0.0 else -t
    print(out)

def comp1(a: list[float]) -> None:
    ys = [x * 2.0 - 1.0 for x in a]  # ail: gpu
    print(ys)

def comp2(lo: int, hi: int) -> None:
    ys = [float(i) * 0.5 for i in range(lo, hi)]  # ail: gpu
    print(ys)

def gather(a: list[float], idx: list[int]) -> None:
    n = len(idx)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[idx[i]]
    print(out)

def inner(a: list[float], w: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        acc = 0.0
        for j in range(len(w)):
            acc += a[i] * w[j]
        out[i] = acc
    print(out)

def minmax(a: list[float], b: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = min(a[i], b[i]) * 3.0 + max(a[i], b[i]) + abs(a[i]) + twice(b[i])
    print(out)

def branchy(a: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        y = a[i]
        if y > 10.0:
            y = y - 10.0
        elif y < -10.0:
            y = y + 10.0
        else:
            y = y * 0.5
        out[i] = y
    print(out)

def short(a: list[float]) -> None:
    out = [0.0] * 2
    # ail: gpu
    for i in range(len(a)):
        out[i] = a[i] + 1.0
    print(out)

def shifted(a: list[float]) -> None:
    out = [0.0] * 4
    # ail: gpu
    for i in range(-2, 2):
        out[i] = a[i] * 2.0
    print(out)

def mixed(a: list[float], b: list[int]) -> None:
    n = len(a)
    cs = [1 if b[i] < a[i] else 0 for i in range(n)]  # ail: gpu
    print(cs)

def main() -> None:
    inf = 1e308 * 10.0
    nan = inf - inf
    fmap([1.5, -2.0, 3.0], [2.0, 4.0, 0.5], 0.25)
    fmap([], [], 1.0)
    fmap([2.0], [3.0], 1.0)
    fmap([inf, -0.0, 0.0, 1e308], [2.0, 1.0, -1.0, 10.0], 1.0)
    fmap([nan, 1.0], [1.0, 1.0], 1.0)
    fmap([5e-324, 1.0], [1.0, 1.0], 1.0)
    fmap([1e-200, 1.0], [1e-200, 1.0], 1.0)
    fmap([1.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0], 0.5)
    try:
        fmap([1.0, 2.0, 3.0], [1.0, 2.0], 1.0)
    except IndexError as e:
        print('IndexError', e)
    comp1([0.5, 1.5, 2.5, -0.0])
    comp1([])
    comp1([nan])
    comp2(3, 7)
    comp2(5, 5)
    comp2(-3, 2)
    comp2(9, 2)
    gather([1.5, 2.5, 3.5], [0, 2, -1, 1, -3])
    gather([1.5, 2.5, 3.5], [])
    try:
        gather([1.5, 2.5, 3.5], [0, 3])
    except IndexError as e:
        print('IndexError', e)
    try:
        gather([1.5, 2.5, 3.5], [-4])
    except IndexError as e:
        print('IndexError', e)
    inner([1.0, 2.0, 3.0], [0.5, 0.25])
    inner([1.0, 2.0], [])
    minmax([0.0, -0.0, 1.0, -1.0], [-0.0, 0.0, -2.0, 2.0])
    minmax([1.5], [1.5])
    branchy([30.0, -30.0, 4.0, 10.0, -10.0, -0.0])
    shifted([1.0, 2.0, 3.0, 4.0])
    short([1.0, 2.0])
    try:
        short([1.0, 2.0, 3.0])
    except IndexError:
        print('IndexError')
    mixed([1.5, 2.5], [1, 3])
    mixed([9007199254740992.0], [9007199254740993])
    mixed([], [])

main()
'''

INT_PROGRAM = r'''
import math

def imap(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * b[i] + 3
    print(out)

def idiv(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] // b[i] + a[i] % b[i]
    print(out)

def imod(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] % b[i]
    print(out)

def itrunc(a: list[float]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = int(a[i])
    print(out)

def floors(a: list[float]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = math.floor(a[i])
    print(out)

def ceils(a: list[float]) -> None:
    ys = [math.ceil(x) for x in a]  # ail: gpu
    print(ys)

def flags(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = (a[i] > b[i]) + (a[i] == b[i]) * 2 + (not a[i] < 0) * 4
    print(out)

def pick(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] if a[i] > b[i] else b[i]
    print(out)

def logic(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = (a[i] and b[i]) + (a[i] or b[i]) * 10
    print(out)

def scaled(a: list[int]) -> None:
    xs = [float(x) * 0.5 + x for x in a]  # ail: gpu
    print(xs)

def main() -> None:
    imap([1, 2, 3], [4, 5, 6])
    imap([], [])
    imap([4611686018427387903, -3], [1, 1])
    idiv([7, -7, 7, -7, 0], [2, 2, -2, -2, 5])
    imod([9223372036854775807, -9223372036854775807, 5], [3, -3, -1])
    try:
        idiv([1, 2, 3], [1, 0, 1])
    except ZeroDivisionError as e:
        print('ZeroDivisionError', e)
    try:
        imod([1, 2, 3], [1, 1, 0])
    except ZeroDivisionError as e:
        print('ZeroDivisionError', e)
    itrunc([1.9, -1.9, 0.5, -0.5, 9e18, -9e18])
    floors([1.5, -1.5, 2.0, -0.0, 4503599627370497.5])
    ceils([1.5, -1.5, 2.0, -0.5])
    flags([3, -3, 0, 5], [3, 4, -1, 2])
    pick([3, -3, 0, 5], [3, 4, -1, 2])
    logic([3, 0, 0, 5], [0, 0, 7, 2])
    scaled([1, 2, 3, 9007199254740993])

main()
'''

OVERFLOW_PROGRAM = r'''
def add(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] + b[i]
    print(out)

def mul(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * b[i]
    print(out)

def fdiv(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] // b[i]
    print(out)

def mod(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] % b[i]
    print(out)

def neg(a: list[int]) -> None:
    ys = [-x for x in a]  # ail: gpu
    print(ys)

def absolute(a: list[int]) -> None:
    ys = [abs(x) for x in a]  # ail: gpu
    print(ys)

def sub(a: list[int], b: list[int]) -> None:
    ys = [a[i] - b[i] for i in range(len(a))]  # ail: gpu
    print(ys)

def trunc(a: list[float]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = int(a[i])
    print(out)

def main() -> None:
    which = int(input())
    huge = 1e308 * 10.0
    nan = huge - huge
    top = 9223372036854775807
    low = -9223372036854775807
    low = low - 1
    if which == 0:
        add([top - 1, 5, low], [1, 1, 0])
    elif which == 1:
        add([top, 5], [1, 1])
    elif which == 2:
        add([low, 5], [-1, 1])
    elif which == 3:
        mul([3037000499, 2], [3037000499, 3])
    elif which == 4:
        mul([3037000500, 2], [3037000500, 3])
    elif which == 5:
        mul([low, 1], [1, 1])
        mul([low, 1], [-1, 1])
    elif which == 6:
        fdiv([low, top, -7], [1, -1, 2])
        mod([low, top, -7], [-1, -1, 2])
    elif which == 7:
        fdiv([low, 5], [-1, 2])
    elif which == 8:
        neg([top, low + 1, 0])
        absolute([top, low + 1, 0])
    elif which == 9:
        neg([low, 5])
    elif which == 10:
        absolute([low, 5])
    elif which == 11:
        sub([low, 0, top], [0, top, low + 1])
    elif which == 12:
        sub([low, 0, top], [1, top, low])
    elif which == 13:
        trunc([1.5, 9.3e18])
    elif which == 14:
        trunc([1.5, nan])
    elif which == 15:
        trunc([1.5, huge])
    elif which == 16:
        trunc([-9.2e18, 9.2e18, -0.5])
    print('done')

main()
'''


def strip_markers(text):
    """The same program without its `# ail: gpu` comments."""
    return re.sub(r'\n[ ]*# ail: gpu(?=\n)', '', text).replace('  # ail: gpu', '')


# the launches of FLOAT_PROGRAM in call order: k<site> n=<elements> ran on the kernel; "replay" = the flag was set and
# the original loop ran; "cpu" = the glue did not launch (the range does not fit the output list)
FLOAT_TRACE = [
    'gpu: k0 n=3 device=emulation',                      # fmap, three elements
    'gpu: k0 n=1 device=emulation',                      # one element (the empty list launches nothing)
    'gpu: k0 n=4 device=emulation',                      # inf, -0.0, 0.0, 1e308 * 10.0
    'gpu: k0 replay flags=0x10 (nan )',                  # a NaN element
    'gpu: k0 replay flags=0x8 (denormal )',              # 5e-324
    'gpu: k0 replay flags=0x8 (denormal )',              # 1e-200 * 1e-200 underflows
    'gpu: k0 n=3 device=emulation',                      # b longer than a: a decides the length
    'gpu: k0 replay flags=0x1 (index )',                 # b shorter than a: IndexError, found by the CPU loop
    'gpu: k1 n=4 device=emulation',                      # comp1
    'gpu: k1 replay flags=0x10 (nan )',
    'gpu: k2 n=4 device=emulation',                      # comp2 over range(3, 7); range(5, 5) and range(9, 2) launch nothing
    'gpu: k2 n=5 device=emulation',                      # range(-3, 2)
    'gpu: k3 n=5 device=emulation',                      # gather with negative indexes
    'gpu: k3 replay flags=0x1 (index )',                 # idx 3 of 3
    'gpu: k3 replay flags=0x1 (index )',                 # idx -4 of 3
    'gpu: k4 n=3 device=emulation',                      # inner loop
    'gpu: k4 n=2 device=emulation',                      # an empty inner range
    'gpu: k5 n=4 device=emulation',                      # min/max/abs/inlined call, signed zeros
    'gpu: k5 n=1 device=emulation',
    'gpu: k6 n=6 device=emulation',                      # if / elif / else
    'gpu: k8 cpu (the range does not fit the output list, or it overlaps an input)',    # range(-2, 2): negative start
    'gpu: k7 n=2 device=emulation',                      # short, output of 2 for 2 elements
    'gpu: k7 cpu (the range does not fit the output list, or it overlaps an input)',    # 3 elements into 2
    'gpu: k9 n=2 device=emulation',                      # int against float
    'gpu: k9 replay flags=0x20 (range )',                # 2**53 + 1 against a float
]

INT_TRACE = [
    'gpu: k0 n=3 device=emulation',                      # imap (the empty call launches nothing)
    'gpu: k0 n=2 device=emulation',                      # 2**62 - 1 + 3 stays in range
    'gpu: k1 n=5 device=emulation',                      # idiv with every sign
    'gpu: k2 n=3 device=emulation',                      # imod near the int64 limits
    'gpu: k1 replay flags=0x2 (zero-division )',         # idiv by 0
    'gpu: k2 replay flags=0x2 (zero-division )',         # imod by 0
    'gpu: k3 n=6 device=emulation',                      # int(float)
    'gpu: k4 n=5 device=emulation',                      # math.floor
    'gpu: k5 n=4 device=emulation',                      # math.ceil in a comprehension
    'gpu: k6 n=4 device=emulation',                      # bool arithmetic
    'gpu: k7 n=4 device=emulation',                      # conditional expression
    'gpu: k8 n=4 device=emulation',                      # and / or as values
    'gpu: k9 n=4 device=emulation',                      # float(x) * 0.5 + x
]


class Eligible(Base):
    """GPU.md 1.1 loops through `compile --gpu` on the typed path."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.float_gpu = Build(cls.dir, 'float_gpu', FLOAT_PROGRAM)
        cls.float_cpu = Build(cls.dir, 'float_cpu', FLOAT_PROGRAM, gpu=False)
        cls.float_bare = Build(cls.dir, 'float_bare', strip_markers(FLOAT_PROGRAM), gpu=False)
        cls.float_bare_gpu = Build(cls.dir, 'float_bare_gpu', strip_markers(FLOAT_PROGRAM), gpu=True)
        cls.int_gpu = Build(cls.dir, 'int_gpu', INT_PROGRAM)
        cls.int_cpu = Build(cls.dir, 'int_cpu', INT_PROGRAM, gpu=False)

    def check_program(self, gpu_build, cpu_build, text, trace):
        for b in (gpu_build, cpu_build):
            self.assertEqual(b.returncode, 0, b.stderr + b.stdout)
        want_out, want_rc = self.expect(text)
        self.assertEqual(want_rc, 0)
        out, rc, err = gpu_build.run(AIL_GPU_TRACE='1')
        self.assertEqual((out, rc), (want_out, want_rc))
        self.assertEqual(trace_lines(err), trace)
        # the rule of GPU.md 0: the same binary with AIL_GPU=0, and the build without --gpu, print the same
        out0, rc0, err0 = gpu_build.run(AIL_GPU='0', AIL_GPU_TRACE='1')
        self.assertEqual((out0, rc0, trace_lines(err0)), (want_out, want_rc, []))
        out1, rc1, err1 = cpu_build.run(AIL_GPU_TRACE='1')
        self.assertEqual((out1, rc1, trace_lines(err1)), (want_out, want_rc, []))

    def test_float_loops_match_cpython_and_replay_on_the_flags(self):
        self.check_program(self.float_gpu, self.float_cpu, FLOAT_PROGRAM, FLOAT_TRACE)

    def test_int_loops_match_cpython_and_replay_on_the_flags(self):
        self.check_program(self.int_gpu, self.int_cpu, INT_PROGRAM, INT_TRACE)

    def test_the_glue_checks_the_output_range_and_overlap_before_a_launch(self):
        c = self.float_gpu.c
        self.assertIn('gk_disjoint(', c)                           # an output that shares memory with an input
        self.assertIn('_gk_lo >= 0 && _gk_hi <=', c)               # a range that fits the output list
        self.assertEqual(len(re.findall(r'static unsigned ail_gk\d+\(', c)), 10)

    def test_every_kernel_is_compiled_into_the_typed_function_it_belongs_to(self):
        c = self.int_gpu.c
        self.assertEqual(len(re.findall(r'static unsigned ail_gk\d+\(', c)), 10)
        self.assertIn('CPU emulation, GPU.md G1', c)

    def test_a_marker_without_gpu_is_a_plain_comment_and_the_loop_runs_on_the_cpu(self):
        self.assertNotIn('ail_gk', self.float_cpu.c)
        self.assertNotIn('gpu', self.float_cpu.stderr.lower())
        self.assertNotIn('ail: gpu', self.float_cpu.stderr)

    def test_programs_without_a_marker_generate_the_same_c_with_or_without_the_switch(self):
        base = self.float_bare.c
        self.assertEqual(self.float_bare_gpu.c, base)
        self.assertEqual(self.float_cpu.c, base)                   # a marker without --gpu changes nothing either
        self.assertNotEqual(self.float_gpu.c, base)
        self.assertEqual(self.float_bare.exe.read_bytes(), self.float_bare_gpu.exe.read_bytes())
        self.assertEqual(self.float_bare.exe.read_bytes(), self.float_cpu.exe.read_bytes())

    def test_the_environment_switch_is_the_flag(self):
        b = Build(self.dir, 'float_env', FLOAT_PROGRAM, gpu=False, env={'AIL_GPU_BUILD': '1'})
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertEqual(b.c, self.float_gpu.c)

    def test_a_script_with_marked_loops_over_module_level_lists(self):
        text = '''
xs = [1.5, 2.5, 3.5, 4.5]
ks = [1, 2, 3]
K = 3
out = [0.0] * len(xs)
# ail: gpu
for i in range(len(xs)):
    out[i] = xs[i] * 2.0 + ks[1] + K
print(out)
ys = [x * K - 1.0 for x in xs]  # ail: gpu
print(ys)
'''
        b = self.build('script', text)
        want = self.expect(text)
        out, rc, err = b.run(AIL_GPU_TRACE='1')
        self.assertEqual((out, rc), want)
        self.assertEqual(trace_lines(err), ['gpu: k0 n=4 device=emulation', 'gpu: k1 n=4 device=emulation'])


class Integers(Base):
    """Values at the int64 limits.  The typed path keeps int64 and stops loudly on overflow (BIGINT.md, DIFFERENCES C288);
    a kernel that meets an overflow sets the flag and the CPU loop produces that behaviour, so the GPU build equals the
    CPU build.  The exact general path (no kernels) equals CPython."""

    IN_RANGE = (0, 3, 6, 8, 16)
    FLAGS = {0: None, 1: 'overflow', 2: 'overflow', 3: None, 4: 'overflow', 5: 'overflow', 6: None, 7: 'overflow',
             8: None, 9: 'overflow', 10: 'overflow', 11: 'overflow', 12: 'overflow', 13: 'range', 14: 'nan',
             15: 'range', 16: None}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.typed = Build(cls.dir, 'overflow_typed', OVERFLOW_PROGRAM)
        cls.general = Build(cls.dir, 'overflow_general', OVERFLOW_PROGRAM, env={'AIL_UNIFIED_FORCE': '1'},
                            typed_only=False)
        path = cls.dir / 'overflow_cpython.py'
        path.write_text(OVERFLOW_PROGRAM.lstrip('\n'), encoding='utf-8')
        cls.cpython = path

    def test_every_case(self):
        self.assertEqual(self.typed.returncode, 0, self.typed.stderr)
        self.assertEqual(self.general.returncode, 0, self.general.stderr)
        for case, flag in sorted(self.FLAGS.items()):
            with self.subTest(case=case):
                stdin = '%d\n' % case
                want_out, want_rc = run_python(self.cpython, stdin)
                out, rc, err = self.typed.run(stdin, AIL_GPU_TRACE='1')
                out0, rc0, err0 = self.typed.run(stdin, AIL_GPU='0')
                self.assertEqual((out, rc), (out0, rc0))                 # the GPU build is the CPU build
                gen_out, gen_rc, _ = self.general.run(stdin)
                self.assertEqual((gen_out, gen_rc), (want_out, want_rc))  # the exact path is CPython
                replays = [line for line in trace_lines(err) if 'replay' in line]
                if flag is None:
                    self.assertEqual(replays, [])
                    self.assertTrue(trace_lines(err), 'no launch ran')
                    self.assertEqual((out, rc), (want_out, want_rc))
                else:
                    self.assertEqual(len(replays), 1, err)
                    self.assertIn('(%s )' % flag, replays[0])
                    self.assertNotEqual(rc, 0)                                # the CPU build stops, loudly
                    quiet = '\n'.join(l for l in err.splitlines() if not l.startswith('gpu: '))
                    self.assertEqual(quiet.strip(), err0.strip())             # with the CPU build's own message

    def test_the_cpu_build_stops_with_its_own_message_on_int64_overflow(self):
        out, rc, err = self.typed.run('1\n', AIL_GPU_TRACE='1')
        self.assertEqual((out, rc), ('', 1))
        self.assertIn('integer overflow', err)
        self.assertIn('replay flags=0x4 (overflow )', err)

    def test_values_just_inside_the_limits_run_on_the_kernel(self):
        out, rc, err = self.typed.run('0\n', AIL_GPU_TRACE='1')
        self.assertEqual(out, '[9223372036854775807, 6, -9223372036854775808]\ndone\n')
        self.assertEqual(trace_lines(err), ['gpu: k0 n=3 device=emulation'])
        out, rc, err = self.typed.run('3\n', AIL_GPU_TRACE='1')
        self.assertEqual(out, '[9223372030926249001, 6]\ndone\n')

    def test_int64_min_over_minus_one_and_modulo_minus_one(self):
        out, rc, err = self.typed.run('6\n', AIL_GPU_TRACE='1')
        self.assertEqual(out, '[-9223372036854775808, -9223372036854775807, -4]\n[0, 0, 1]\ndone\n')
        out, rc, err = self.typed.run('7\n', AIL_GPU_TRACE='1')
        self.assertEqual(rc, 1)
        self.assertIn('replay flags=0x4 (overflow )', err)


class General(Base):
    """GPU.md 1: the general path never offloads.  A marked loop there runs on the CPU and prints the same."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.general = Build(cls.dir, 'float_general', FLOAT_PROGRAM, env={'AIL_UNIFIED_FORCE': '1'}, typed_only=False)

    def test_same_output_no_kernel_and_a_note_per_loop(self):
        b = self.general
        self.assertEqual(b.returncode, 0, b.stderr)
        want_out, want_rc = self.expect(FLOAT_PROGRAM)
        out, rc, err = b.run(AIL_GPU_TRACE='1')
        self.assertEqual((out, rc), (want_out, want_rc))
        self.assertEqual(trace_lines(err), [])
        self.assertNotIn('ail_gk', b.c)
        notes = [line for line in b.stderr.splitlines() if "'# ail: gpu' ignored" in line]
        self.assertEqual(len(notes), 10)
        self.assertTrue(all('the general path never offloads' in line for line in notes))
        self.assertIn('float_general.py:8:', notes[0])

    def test_a_function_that_needs_tagged_ints_is_built_on_the_general_path(self):
        text = '''
def f(a: list[float], k: int) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * k + i
    print(out)

f([1.5, 2.5], 3)
'''
        b = Build(self.dir, 'tagged', text, typed_only=False)
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertIn("'# ail: gpu' ignored", b.stderr)
        out, rc, err = b.run(AIL_GPU_TRACE='1')
        self.assertEqual((out, rc), self.expect(text))
        self.assertEqual(trace_lines(err), [])


# ---------------------------------------------------------------------------------------------------- refusals
HEAD = '''
import math

def twice(x: float) -> float:
    return x * 2.0

def two_returns(x: float) -> float:
    if x > 0.0:
        return x
    return -x

def untyped(x):
    return x

def rec(x: int) -> int:
    return rec(x - 1) if x > 0 else 0

def f(a: list[float], b: list[float], k: float) -> None:
    n = len(a)
    out = [0.0] * n
'''
HEAD_LINES = HEAD.lstrip('\n').count('\n')
TAIL = '\n\nf([1.0], [2.0], 1.0)\n'

# name, body (in f), expected substrings of the message, line (of the body) of the refused statement
REFUSALS = [
    ('while', '    i = 0\n    # ail: gpu\n    while i < n:\n        out[i] = a[i]\n        i += 1\n', 3,
     ['a while loop', 'write instead: use `for i in range(n)`']),
    ('step', '    # ail: gpu\n    for i in range(0, n, 2):\n        out[i] = a[i]\n', 2,
     ['only `for i in range(a)` and `for i in range(a, b)`', 'write instead: loop over the index']),
    ('iterate a list', '    # ail: gpu\n    for x in a:\n        out[0] = x\n', 2, ['only `for i in range(a)`']),
    ('for else', '    # ail: gpu\n    for i in range(n):\n        out[i] = a[i]\n    else:\n        pass\n', 2,
     ['a `for ... else` loop', 'remove the else branch']),
    ('no store', '    # ail: gpu\n    for i in range(n):\n        t = a[i]\n', 2,
     ['does not end with a store `out[i] = <expr>`', 'write instead: end the body with']),
    ('accumulate', '    s = 0.0\n    for i in range(n):  # ail: gpu\n        s += a[i]\n', 2,
     ['a reduction (stage G6)']),
    ('running total', '    s = 0.0\n    # ail: gpu\n    for i in range(n):\n        s += a[i]\n        out[i] = s\n', 4,
     ["'s' is read before the body assigns it", 'sums and counters are stage G6', 'write instead']),
    ('sum', '    s = sum(x * x for x in a)  # ail: gpu\n', 1, ['sum(...) is a reduction (stage G6)']),
    ('not a loop', '    # ail: gpu\n    n = n + 1\n', 2, ['the marker is not on a `for` loop', 'it is on an assignment']),
    ('print', '    # ail: gpu\n    for i in range(n):\n        print(i)\n        out[i] = a[i]\n', 3,
     ['a call or expression statement (print, append, a helper) is not allowed', 'write instead: compute values']),
    ('append', '    ys = []\n    # ail: gpu\n    for i in range(n):\n        ys.append(a[i])\n        out[i] = a[i]\n',
     4, ['a call or expression statement']),
    ('break', '    # ail: gpu\n    for i in range(n):\n        if a[i] > 1.0:\n            break\n        out[i] = a[i]\n',
     4, ['break is not available', 'write instead: make the loop body a straight computation']),
    ('math.exp', '    # ail: gpu\n    for i in range(n):\n        out[i] = math.exp(a[i])\n', 3,
     ['math.exp has no exact GPU form', "write instead: drop '# ail: gpu' (the loop runs on the CPU) or move the "
                                        'math.exp call out of the loop']),
    ('math.sqrt', '    # ail: gpu\n    for i in range(n):\n        out[i] = math.sqrt(a[i])\n', 3,
     ['math.sqrt needs the correctly rounded GPU square root of stage G5']),
    ('float division', '    # ail: gpu\n    for i in range(n):\n        out[i] = a[i] / b[i]\n', 3,
     ['`/` needs the correctly rounded GPU division of stage G5', 'write instead: compute with']),
    ('power', '    # ail: gpu\n    for i in range(n):\n        out[i] = a[i] ** 2\n', 3, ['`**` has no exact GPU form']),
    ('float modulo', '    # ail: gpu\n    for i in range(n):\n        out[i] = a[i] % 3.0\n', 3,
     ['float `%` has no exact GPU form (libm)']),
    ('shift', '    m = [0] * n\n    # ail: gpu\n    for i in range(n):\n        m[i] = i << 2\n', 4,
     ['`<<` is not available on the GPU yet']),
    ('round', '    m = [0] * n\n    # ail: gpu\n    for i in range(n):\n        m[i] = round(a[i])\n', 4,
     ['round() has no exact GPU form']),
    ('read the output', '    # ail: gpu\n    for i in range(n):\n        out[i] = out[i] + a[i]\n', 3,
     ["the output list 'out' is also read in the body", 'a loop that reads what it writes']),
    ('length of the output', '    # ail: gpu\n    for i in range(n):\n        out[i] = a[i] + len(out)\n', 3,
     ["the output list 'out' is also read in the body"]),
    ('two stores', '    # ail: gpu\n    for i in range(n):\n        out[0] = a[i]\n        out[i] = a[i]\n', 3,
     ['a store other than the last statement `out[i] = <expr>`']),
    ('string constant', '    # ail: gpu\n    for i in range(n):\n        out[i] = a[i] + len("ab")\n', 3,
     ['len() takes a list name']),
    ('None constant', '    # ail: gpu\n    for i in range(n):\n        out[i] = a[i] + None\n', 3,
     ['only int, float and bool constants are allowed']),
    ('tuple assignment', '    # ail: gpu\n    for i in range(n):\n        x, y = a[i], b[i]\n        out[i] = x + y\n',
     3, ['only a local name can be assigned']),
    ('attribute', '    # ail: gpu\n    for i in range(n):\n        out[i] = a[i].real\n', 3, ['an attribute']),
    ('unknown function', '    # ail: gpu\n    for i in range(n):\n        out[i] = foo(a[i])\n', 3,
     ['foo() is not a function a GPU loop body can call']),
    ('recursion', '    m = [0] * n\n    # ail: gpu\n    for i in range(n):\n        m[i] = rec(i)\n', 4,
     ['rec() is recursive']),
    ('two returns', '    # ail: gpu\n    for i in range(n):\n        out[i] = two_returns(a[i])\n', 3,
     ['two_returns() must have a single `return <expr>` as its last statement', 'write instead: rewrite two_returns()']),
    ('unannotated callee', '    # ail: gpu\n    for i in range(n):\n        out[i] = untyped(a[i])\n', 3,
     ['its parameters must be annotated int or float']),
    ('private after the loop', '    t = 0.0\n    # ail: gpu\n    for i in range(n):\n        t = a[i] * 2.0\n'
                               '        out[i] = t\n    print(t)\n', 6,
     ["'t' is assigned inside a GPU loop", 'has no value after the loop']),
    ('different branch types', '    # ail: gpu\n    for i in range(n):\n        out[i] = 1.5 if a[i] > 0.0 else 0\n', 3,
     ['the two branches of the conditional expression have different types (float and int)']),
    ('and/or of different types', '    # ail: gpu\n    for i in range(n):\n        out[i] = 1.5 or 1\n', 3,
     ['the operands of `and`/`or` have different types']),
    ('local changes type', '    # ail: gpu\n    for i in range(n):\n        t = 1\n        t = 2.5\n        out[i] = t\n', 4,
     ["'t' holds an int and then a float"]),
    ('triangular inner loop', '    # ail: gpu\n    for i in range(n):\n        acc = 0.0\n        for j in range(i):\n'
                              '            acc += a[j]\n        out[i] = acc\n', 4,
     ["the bound of an inner loop depends on 'i'"]),
    ('stepped inner loop', '    # ail: gpu\n    for i in range(n):\n        acc = 0.0\n        for j in range(0, 4, 2):\n'
                           '            acc += a[j]\n        out[i] = acc\n', 4, ['an inner loop must be `for j in range(K)`']),
    ('nested markers', '    # ail: gpu\n    for i in range(n):\n        # ail: gpu\n        for j in range(n):\n'
                       '            pass\n        out[i] = a[i]\n', 4, ['a GPU loop inside another GPU loop']),
    ('comprehension filter', '    ys = [x for x in a if x > 0.0]  # ail: gpu\n', 1,
     ['a comprehension with `if` builds a list of data-dependent length', 'filter in an ordinary loop']),
    ('two for clauses', '    ys = [x + y for x in a for y in b]  # ail: gpu\n', 1, ['a comprehension with 2 `for` clauses']),
    ('comprehension over enumerate', '    ys = [x for i, x in enumerate(a)]  # ail: gpu\n', 1,
     ['the comprehension must run over range(a, b), a list name, or zip()']),
    ('comprehension tuple', '    ys = [(x, x) for x in a]  # ail: gpu\n', 1, ['a tuple']),
    ('lambda', '    ys = [(lambda y: y)(x) for x in a]  # ail: gpu\n', 1, ['only plain calls are allowed']),
    ('marker before a call', '    n = n + 1\n    # ail: gpu\n', 5, ['it is on an expression statement']),
]


class Refusals(Base):
    """GPU.md 1.3: a marked loop that is not provably eligible is refused at compile time, by name, with the line, the
    reason and a `write instead:` hint.  The same program without --gpu builds and runs on the CPU."""

    def refusal(self, body):
        import gpu
        text = HEAD.lstrip('\n') + body + TAIL
        with self.assertRaises(gpu.GpuRefusal) as caught:
            gpu.sites_of(text)
        return caught.exception, HEAD_LINES

    def test_each_refusal_names_the_construct_the_line_and_a_hint(self):
        for name, body, offset, wanted in REFUSALS:
            with self.subTest(name):
                error, head = self.refusal(body)
                message = str(error)
                self.assertTrue(message.startswith('GPU loop: '), message)
                self.assertIn('; write instead: ', message)
                for part in wanted:
                    self.assertIn(part, message)
                self.assertEqual(error.source_line, head + offset, message)

    def test_a_marker_at_the_end_of_the_file_marks_nothing(self):
        import gpu
        with self.assertRaises(gpu.GpuRefusal) as caught:
            gpu.sites_of('def f(a):\n    return a\n# ail: gpu\n')
        self.assertIn('is not followed by a statement', str(caught.exception))
        self.assertEqual(caught.exception.source_line, 3)

    def test_the_type_dependent_refusals_of_the_lowering(self):
        cases = [
            ('def f(a, k):\n    out = [0.0] * 3\n    # ail: gpu\n    for i in range(3):\n        out[i] = a[i] if k > 0 else 0\n',
             {'a': ('list', 'f'), 'k': 'f'}, 5, 'the two branches of the conditional expression have different types'),
            ('def f(a, k):\n    out = [0.0] * 3\n    # ail: gpu\n    for i in range(3):\n        out[i] = a[i] or 1\n',
             {'a': ('list', 'f'), 'k': 'f'}, 5, 'the operands of `and`/`or` have different types'),
            ('def f(a, k):\n    out = [0.0] * 3\n    # ail: gpu\n    for i in range(3):\n        out[i] = min(a[i], 1)\n',
             {'a': ('list', 'f'), 'k': 'f'}, 5, 'the arguments of min() are not all ints or all floats'),
            ('def f(a, k):\n    out = [0.0] * 3\n    # ail: gpu\n    for i in range(3):\n        out[i] = a[i] // 2\n',
             {'a': ('list', 'f'), 'k': 'f'}, 5, 'float `//` has no exact GPU form'),
            ('def f(a, k):\n    out = [0.0] * 3\n    # ail: gpu\n    for i in range(3):\n        out[i] = a[i] + a\n',
             {'a': ('list', 'f'), 'k': 'f'}, 5, "the list 'a' is used as a value"),
            ('def f(a, k):\n    out = [0.0] * 3\n    # ail: gpu\n    for i in range(3):\n        out[i] = a[k]\n',
             {'a': ('list', 'f'), 'k': 'f'}, 5, 'a list index must be an int'),
            ('def g(x: int) -> float:\n    return x * 2\n\ndef f(a, k):\n    out = [0.0] * 3\n    # ail: gpu\n'
             '    for i in range(3):\n        out[i] = g(i)\n',
             {'a': ('list', 'f'), 'k': 'f'}, 8, 'g() is declared to return float but returns int'),
            ('def g(x: float) -> float:\n    return x * 2.0\n\ndef f(a, k):\n    out = [0.0] * 3\n    # ail: gpu\n'
             '    for i in range(3):\n        out[i] = g(i)\n',
             {'a': ('list', 'f'), 'k': 'f'}, 8, "argument 'x' of g() is int but the parameter is float"),
        ]
        import gpu
        for source, types, line, wanted in cases:
            with self.subTest(wanted):
                with self.assertRaises(gpu.GpuRefusal) as caught:
                    lower(source, types)
                self.assertIn(wanted, str(caught.exception))
                self.assertIn('write instead: ', str(caught.exception))
                self.assertEqual(caught.exception.source_line, line)

    def test_the_refusals_do_not_depend_on_the_switch_of_the_unmarked_program(self):
        import gpu
        for name, body, offset, wanted in REFUSALS[:6]:
            with self.subTest(name):
                self.assertEqual(gpu.sites_of(strip_markers(HEAD.lstrip('\n') + body + TAIL)), [])

    def run_cli(self, name, text, **env):
        b = Build(self.dir, name, text, **env)
        return b

    def test_the_command_line_names_file_line_column_and_exits_with_3(self):
        cases = [('exp', '    # ail: gpu\n    for i in range(n):\n        out[i] = math.exp(a[i])\n', 3,
                  'math.exp has no exact GPU form'),
                 ('sqrt', '    # ail: gpu\n    for i in range(n):\n        out[i] = math.sqrt(a[i])\n', 3,
                  'math.sqrt needs the correctly rounded GPU square root of stage G5'),
                 ('divide', '    # ail: gpu\n    for i in range(n):\n        out[i] = a[i] / b[i]\n', 3,
                  '`/` needs the correctly rounded GPU division of stage G5'),
                 ('whiled', '    i = 0\n    # ail: gpu\n    while i < n:\n        i += 1\n', 3, 'a while loop'),
                 ('lowered', '    ys = [(x, x) for x in a]  # ail: gpu\n', 1, 'a tuple')]
        for name, body, offset, wanted in cases:
            with self.subTest(name):
                b = self.run_cli('cli_' + name, HEAD + body + TAIL)
                self.assertEqual(b.returncode, 3, b.stderr + b.stdout)
                line = HEAD_LINES + offset
                self.assertIn('cli_%s.py:%d:' % (name, line), b.stderr)
                self.assertIn('not in the subset: GPU loop: ', b.stderr)
                self.assertIn(wanted, b.stderr)
                self.assertIn('write instead: ', b.stderr)
                self.assertFalse(b.exe.exists())

    def test_the_same_programs_build_and_run_without_the_switch(self):
        body = '    # ail: gpu\n    for i in range(n):\n        out[i] = math.exp(a[i]) + a[i] / b[i]\n    print(out)\n'
        b = self.run_cli('noswitch', HEAD + body + TAIL, gpu=False, typed_only=False)
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertNotIn('GPU', b.stderr)
        self.assertEqual(b.run()[:2], self.expect(HEAD + body + TAIL))

    def test_the_typed_half_refuses_what_only_the_types_show(self):
        cases = [
            ('try', 'def f(a: list[float]) -> None:\n    n = len(a)\n    out = [0.0] * n\n    try:\n'
                    '        # ail: gpu\n        for i in range(n):\n            out[i] = a[i] * 2.0\n'
                    '    except IndexError:\n        print("x")\n    print(out)\n\nf([1.5])\n',
             6, 'the function has try/except', 'move the loop into a function without try'),
            ('method', 'class P:\n    def run(self, a: list[float]) -> None:\n        n = len(a)\n        out = [0.0] * n\n'
                       '        # ail: gpu\n        for i in range(n):\n            out[i] = a[i] * 2.0\n'
                       '        print(out)\n\nP().run([1.5])\n',
             1, 'not available in class methods yet', 'move the loop into a top-level function'),
            ('text', 'def f(a: list[float], s: str) -> None:\n    n = len(a)\n    out = [0.0] * n\n    # ail: gpu\n'
                     '    for i in range(n):\n        out[i] = a[i] * len(s)\n    print(out)\n\nf([1.5], "ab")\n',
             6, "'s' is not a list[float] or list[int] the typed path keeps contiguously", 'use list[float] / list[int]'),
        ]
        for name, text, line, wanted, hint in cases:
            with self.subTest(name):
                b = self.run_cli('typed_' + name, text)
                self.assertEqual(b.returncode, 3, b.stderr + b.stdout)
                self.assertIn('typed_%s.py:%d:' % (name, line), b.stderr)
                self.assertIn(wanted, b.stderr)
                self.assertIn(hint, b.stderr)

    def test_the_help_text_names_the_switch(self):
        r = subprocess.run([sys.executable, '-B', str(CLI), 'compile', '--help'], capture_output=True, text=True)
        self.assertIn('--gpu', r.stdout)
        self.assertIn('# ail: gpu', r.stdout)


if __name__ == '__main__':
    unittest.main()
