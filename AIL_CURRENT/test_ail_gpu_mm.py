"""GPU matrix multiply for ail_array (docs/design/TYPED_ARRAY.md 5.7, GPU.md 6.7): python/pkg-v12/gpu_matmul.py.

* `Cpu`      -- the C CPU kernel of the host function equals the pure-Python reference (`ta.dot` of a row and a column) bit for bit,
                on shapes with empty dimensions, 1 x N, N x 1, sizes off every tile, K around the block size 1024, and order-sensitive
                data (1e16, 1, -1e16), signed zeros, inf and NaN.  No Vulkan needed.
* `Errors`   -- the shape, dtype and type errors are the CPU path's own.  No Vulkan needed.
* `Spirv`    -- the four kernels are well-formed words (header, no OpSRem, spirv-val when installed).  No Vulkan needed.
* `Device`   -- the default (exact) kernel on a Vulkan device (lavapipe in CI) equals the reference bit for bit, f64 and f32; the
                opt-in fast kernel is close (and says nothing about bits); the fallbacks (AIL_GPU=0, no loader, a corrupted device, a
                subnormal-risk input) print the same bits.  Skipped without a device; AIL_GPU_REQUIRE_DEVICE=1 turns the skip into a failure.
"""
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
for p in (str(PKG), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import ail_array as ta                         # noqa: E402
import gpu_matmul as gm                        # noqa: E402

CC = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
REQUIRE_DEVICE = os.environ.get('AIL_GPU_REQUIRE_DEVICE', '') not in ('', '0')
SPIRV_VAL = os.environ.get('SPIRV_VAL') or shutil.which('spirv-val')


def need_cc():
    if not CC:
        raise unittest.SkipTest('no C compiler')


def matrix(rows, cols, dt, gen):
    return ta.array([[gen(i, j) for j in range(cols)] for i in range(rows)], dt) if rows and cols else ta.zeros((rows, cols), dt)


def rnd(seed):
    r = random.Random(seed)
    return lambda i, j: r.uniform(-4.0, 4.0) * (2.0 ** r.randint(-6, 6))


def f32_exact(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


# the shapes: (M, K, N)
SHAPES = [(1, 1, 1), (1, 5, 1), (1, 70, 9), (9, 70, 1), (3, 17, 5), (7, 16, 7), (2, 1023, 3), (2, 1024, 3), (3, 1025, 2),
          (2, 2047, 2), (2, 2048, 2), (2, 2049, 3), (2, 3 * 1024 + 7, 2), (2, 5 * 1024 + 13, 3), (33, 70, 31), (65, 33, 64),
          (64, 64, 64), (31, 129, 65)]
EMPTY = [(0, 5, 3), (4, 5, 0), (0, 0, 0), (3, 0, 4), (0, 3, 0), (1, 0, 1)]


def order_sensitive(dt):
    """Data for which only the lane order of TYPED_ARRAY.md 3.7 gives the CPU's bits."""
    big = 1e8 if dt is ta.f32 else 1e16
    return (lambda i, j: (big, 1.0, -big)[j % 3] * (1.0 + i)), (lambda i, j: 1.0 + (j % 2) * 0.5)


def specials(dt):
    """-0.0 products, inf, -inf, NaN, signed zeros in the result."""
    vals = [0.0, -0.0, 1.0, -1.0, 2.5, float('inf'), float('-inf'), float('nan'), 3.0, -0.5]
    r = random.Random(7)
    return (lambda i, j: vals[r.randrange(len(vals))]), (lambda i, j: vals[r.randrange(len(vals))])


class Cpu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_cc()

    def same(self, a, b, what):
        ref = gm.reference_matmul(a, b)
        got = gm.cpu_matmul(a, b)
        self.assertEqual(got.shape, ref.shape, what)
        self.assertEqual(got.tobytes(), ref.tobytes(), what)

    def test_random_shapes(self):
        for dt in (ta.f64, ta.f32):
            for s, (m, k, n) in enumerate(SHAPES):
                a, b = matrix(m, k, dt, rnd(s)), matrix(k, n, dt, rnd(s + 100))
                self.same(a, b, '%s %s' % (dt, (m, k, n)))

    def test_empty_dimensions(self):
        for dt in (ta.f64, ta.f32):
            for (m, k, n) in EMPTY:
                a, b = ta.zeros((m, k), dt), ta.zeros((k, n), dt)
                self.same(a, b, '%s %s' % (dt, (m, k, n)))

    def test_k_zero_is_positive_zero(self):
        c = gm.cpu_matmul(ta.zeros((2, 0), ta.f64), ta.zeros((0, 3), ta.f64))
        self.assertEqual(c.tobytes(), bytes(2 * 3 * 8))

    def test_order_sensitive(self):
        for dt in (ta.f64, ta.f32):
            ga, gb = order_sensitive(dt)
            for (m, k, n) in [(2, 17, 3), (2, 1025, 3), (3, 2100, 2), (1, 5 * 1024 + 13, 2)]:
                self.same(matrix(m, k, dt, ga), matrix(k, n, dt, gb), '%s %s' % (dt, (m, k, n)))

    def test_specials(self):
        for dt in (ta.f64, ta.f32):
            ga, gb = specials(dt)
            for (m, k, n) in [(3, 20, 4), (4, 1030, 3)]:
                a = matrix(m, k, dt, ga)
                b = matrix(k, n, dt, gb)
                self.same(a, b, '%s %s' % (dt, (m, k, n)))

    def test_the_cpu_kernel_is_the_cpu_reference(self):
        """`ta.matmul` (the CPU path of this version, f64) equals the C kernel and the reference built from `ta.dot`."""
        a, b = matrix(5, 1100, ta.f64, rnd(1)), matrix(1100, 4, ta.f64, rnd(2))
        self.assertEqual(ta.matmul(a, b).tobytes(), gm.cpu_matmul(a, b).tobytes())


class Errors(unittest.TestCase):
    def raises(self, a, b):
        errs = []
        for f in (ta.matmul, lambda x, y: gm._check(ta, x, y)):
            try:
                f(a, b)
                errs.append(None)
            except Exception as e:                    # noqa: BLE001
                errs.append((type(e), str(e)))
        return errs

    def test_same_errors_as_the_cpu_path(self):
        z = ta.zeros
        cases = [(ta.array([1.0], ta.f64), z((2, 2), ta.f64)),          # not 2-D
                 (z((2, 2), ta.f64), ta.array([1.0, 2.0], ta.f64)),
                 (z((2, 3), ta.f64), z((4, 5), ta.f64)),                # inner sizes differ
                 (z((2, 3), ta.f64), z((3, 5), ta.f32)),                # dtypes differ
                 (z((2, 3), ta.f16), z((3, 5), ta.f16)),                # dtype not built
                 (z((2, 3), ta.int32), z((3, 5), ta.int32)),
                 (z((0, 3), ta.f64), z((4, 0), ta.f64)),                # empty and mismatched
                 ([[1.0]], z((1, 1), ta.f64))]                          # not arrays
        for a, b in cases:
            cpu, gpu = self.raises(a, b)
            self.assertIsNotNone(cpu)
            self.assertEqual(cpu, gpu)

    def test_valid_shapes_pass(self):
        z = ta.zeros
        self.assertEqual(gm._check(ta, z((2, 3), ta.f64), z((3, 5), ta.f64))[1:], (2, 3, 5))
        self.assertEqual(gm._check(ta, z((0, 3), ta.f64), z((3, 0), ta.f64))[1:], (0, 3, 0))

    def test_f32_is_allowed_on_the_gpu_path_only(self):
        z = ta.zeros
        a, b = z((2, 3), ta.f32), z((3, 5), ta.f32)
        self.assertEqual(gm._check(ta, a, b)[0], ta.f32)
        with self.assertRaises(TypeError):
            ta.matmul(a, b)                 # the CPU path of this version builds f64 only (TYPED_ARRAY.md 3.7)


class Spirv(unittest.TestCase):
    def test_modules_are_well_formed(self):
        ks = gm.kernels()
        self.assertEqual(sorted(ks), ['exact_f32', 'exact_f64', 'fast_f32', 'fast_f64'])
        for name, words in ks.items():
            self.assertEqual(words[0], 0x07230203, name)
            self.assertEqual(words[1], 0x00010400, name)
            self.assertGreater(words[3], 10, name)
            ops, i = [], 5
            while i < len(words):
                n = words[i] >> 16
                self.assertGreater(n, 0, name)
                ops.append(words[i] & 0xFFFF)
                i += n
            self.assertEqual(i, len(words), name)
            self.assertNotIn(138, ops, name + ': OpSRem is wrong for 64-bit operands on NVIDIA 580 (GPU.md 6.3)')
            self.assertNotIn(139, ops, name + ': OpSMod')
            self.assertNotIn(137, ops, name + ': OpUMod is not needed')
            self.assertNotIn(12, ops, name + ': no extended instruction (no FMA, no FMin/FMax)')

    def test_exact_kernels_decorate_every_float_op_no_contraction(self):
        for name in ('exact_f64', 'exact_f32'):
            words = gm.kernels()[name]
            fops, deco, i = [], set(), 5
            while i < len(words):
                n, op = words[i] >> 16, words[i] & 0xFFFF
                if op in (129, 133):                 # OpFAdd, OpFMul: result id is operand 2
                    fops.append(words[i + 2])
                if op == 71 and words[i + 2] == 42:  # OpDecorate target NoContraction
                    deco.add(words[i + 1])
                i += n
            self.assertGreater(len(fops), 40, name)
            self.assertEqual(set(fops) - deco, set(), name)

    def test_the_fast_kernels_do_not_pin_the_arithmetic(self):
        words = gm.kernels()['fast_f64']
        i, nc = 5, 0
        while i < len(words):
            n, op = words[i] >> 16, words[i] & 0xFFFF
            if op == 71 and words[i + 2] == 42:
                nc += 1
            i += n
        self.assertEqual(nc, 0)

    def test_spirv_val(self):
        if not SPIRV_VAL:
            raise unittest.SkipTest('no spirv-val (apt install spirv-tools)')
        import tempfile
        for name, words in gm.kernels().items():
            with tempfile.NamedTemporaryFile(suffix='.spv', delete=False) as f:
                f.write(struct.pack('<%dI' % len(words), *words))
            try:
                r = subprocess.run([SPIRV_VAL, '--target-env', 'vulkan1.2', f.name], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, name + '\n' + r.stderr[:2000])
            finally:
                os.unlink(f.name)


def have_device():
    need_cc()
    a = ta.zeros((2, 2), ta.f64)
    gm.matmul(a, a)
    return gm.last_device() != 'cpu'


class Device(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_cc()
        cls.dev = have_device()

    def setUp(self):
        if not self.dev:
            if REQUIRE_DEVICE:
                self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set: %s' % gm.last_reason())
            raise unittest.SkipTest('no Vulkan device (install mesa-vulkan-drivers for lavapipe)')

    def exact(self, a, b, what):
        ref = gm.reference_matmul(a, b)
        got = gm.matmul(a, b)
        self.assertEqual(gm.last_device() != 'cpu', True, '%s: ran on the CPU (%s)' % (what, gm.last_reason()))
        self.assertEqual(got.shape, ref.shape, what)
        self.assertEqual(got.tobytes(), ref.tobytes(), what)

    def test_random_shapes_bit_identical(self):
        for dt in (ta.f64, ta.f32):
            for s, (m, k, n) in enumerate(SHAPES):
                a, b = matrix(m, k, dt, rnd(s)), matrix(k, n, dt, rnd(s + 100))
                self.exact(a, b, '%s %s' % (dt, (m, k, n)))

    def test_order_sensitive_bit_identical(self):
        for dt in (ta.f64, ta.f32):
            ga, gb = order_sensitive(dt)
            for (m, k, n) in [(2, 17, 3), (2, 1025, 3), (3, 2100, 2), (1, 5 * 1024 + 13, 2), (70, 2049, 3)]:
                self.exact(matrix(m, k, dt, ga), matrix(k, n, dt, gb), '%s %s' % (dt, (m, k, n)))

    def test_specials_bit_identical(self):
        for dt in (ta.f64, ta.f32):
            ga, gb = specials(dt)
            for (m, k, n) in [(3, 20, 4), (4, 1030, 3), (9, 17, 9)]:
                self.exact(matrix(m, k, dt, ga), matrix(k, n, dt, gb), '%s %s' % (dt, (m, k, n)))

    def test_large_k_many_blocks(self):
        a, b = matrix(2, 70 * 1024 + 5, ta.f64, rnd(11)), matrix(70 * 1024 + 5, 2, ta.f64, rnd(12))
        self.assertEqual(gm.matmul(a, b).tobytes(), gm.cpu_matmul(a, b).tobytes())

    def test_empty_dimensions(self):
        for dt in (ta.f64, ta.f32):
            for (m, k, n) in EMPTY:
                a, b = ta.zeros((m, k), dt), ta.zeros((k, n), dt)
                got = gm.matmul(a, b)
                self.assertEqual(got.shape, (m, n))
                self.assertEqual(got.tobytes(), bytes(m * n * dt.itemsize))
                got = gm.matmul(a, b, fast=True)
                self.assertEqual(got.tobytes(), bytes(m * n * dt.itemsize))

    def test_fast_kernel_is_close_not_identical_by_contract(self):
        for dt, tol in ((ta.f64, 1e-9), (ta.f32, 1e-3)):
            for (m, k, n) in [(1, 7, 1), (1, 70, 9), (9, 70, 1), (33, 70, 31), (65, 33, 64), (64, 64, 64), (31, 129, 65), (4, 3000, 5)]:
                a = matrix(m, k, dt, lambda i, j: (((i * 31 + j * 17) % 23) - 11) / 8.0)
                b = matrix(k, n, dt, lambda i, j: (((i * 13 + j * 7) % 19) - 9) / 8.0)
                ref = gm.reference_matmul(a, b).tolist()
                got = gm.matmul(a, b, fast=True)
                self.assertEqual(got.shape, (m, n))
                self.assertTrue(gm.last_device() != 'cpu', gm.last_reason())
                for r, row in enumerate(got.tolist()):
                    for c, x in enumerate(row):
                        self.assertTrue(abs(x - ref[r][c]) <= tol * max(1.0, abs(ref[r][c])) * max(1, k) ** 0.5,
                                        '%s %s [%d, %d]: %r vs %r' % (dt, (m, k, n), r, c, x, ref[r][c]))

    def test_the_subnormal_guard_keeps_tiny_inputs_on_the_cpu_with_the_same_bits(self):
        a = ta.array([[1e-300, 2e-300, 0.0, 1e-310]], ta.f64)
        b = ta.array([[1e-10], [3e-9], [1.0], [1e-5]], ta.f64)
        a2 = ta.array([[1e-300, -1e-300, 1e-300]], ta.f64)
        b2 = ta.array([[1e-30], [1e-30], [1.0000000000000002e-30]], ta.f64)
        for x, y in ((a, b), (a2, b2)):
            got = gm.matmul(x, y)
            self.assertEqual(got.tobytes(), gm.reference_matmul(x, y).tobytes())
            self.assertEqual(gm.last_device(), 'cpu')
            self.assertIn('subnormal', gm.last_reason())

    def test_gpu_off_runs_the_cpu_kernel(self):
        a, b = matrix(5, 40, ta.f64, rnd(3)), matrix(40, 6, ta.f64, rnd(4))
        old = os.environ.get('AIL_GPU')
        os.environ['AIL_GPU'] = '0'
        try:
            got = gm.matmul(a, b)
            self.assertEqual(gm.last_device(), 'cpu')
        finally:
            if old is None:
                os.environ.pop('AIL_GPU')
            else:
                os.environ['AIL_GPU'] = old
        self.assertEqual(got.tobytes(), gm.reference_matmul(a, b).tobytes())


SNIPPET = r'''
import sys
sys.path[:0] = [%(pkg)r, %(root)r]
import ail_array as ta, gpu_matmul as gm
a = ta.array([[(i * 7 + j * 3) %% 11 / 4.0 - 1.0 for j in range(40)] for i in range(5)], ta.f64)
b = ta.array([[(i * 5 + j * 9) %% 13 / 4.0 - 1.5 for j in range(6)] for i in range(40)], ta.f64)
got = gm.matmul(a, b)
print(gm.last_device() != 'cpu', got.tobytes() == gm.reference_matmul(a, b).tobytes())
'''


class Fallbacks(unittest.TestCase):
    """Whole-process fallbacks, each in its own process (the device state is per process)."""

    @classmethod
    def setUpClass(cls):
        need_cc()

    def run_with(self, **env):
        e = dict(os.environ)
        for k in ('AIL_GPU', 'AIL_VULKAN_LIB', 'AIL_GPU_INJECT', 'AIL_GPU_DISABLE', 'AIL_GPU_DEVICE', 'AIL_GPU_CHECK'):
            e.pop(k, None)
        e.update(env)
        r = subprocess.run([sys.executable, '-B', '-c', SNIPPET % dict(pkg=str(PKG), root=str(ROOT))], capture_output=True, text=True,
                           env=e, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return r.stdout.split(), r.stderr

    def test_no_vulkan_loader(self):
        out, _ = self.run_with(AIL_VULKAN_LIB='/nonexistent/libvulkan.so.1')
        self.assertEqual(out, ['False', 'True'])

    def test_gpu_off(self):
        out, _ = self.run_with(AIL_GPU='0')
        self.assertEqual(out, ['False', 'True'])

    def test_device_without_float_controls_is_not_used(self):
        out, _ = self.run_with(AIL_GPU_DISABLE='rte')
        self.assertEqual(out, ['False', 'True'])

    def test_a_corrupted_device_is_caught_by_the_selftest(self):
        base, _ = self.run_with()
        if base[0] != 'True':
            if REQUIRE_DEVICE:
                self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set')
            raise unittest.SkipTest('no Vulkan device')
        out, err = self.run_with(AIL_GPU_INJECT='flip', AIL_GPU_TRACE='1')
        self.assertEqual(out, ['False', 'True'])
        self.assertIn('FAILED', err)

    def test_the_device_when_there_is_one(self):
        out, err = self.run_with()
        self.assertEqual(out[1], 'True')


if __name__ == '__main__':
    unittest.main()
