"""Job fdarr3 (docs/design/TYPED_ARRAY.md T3b): f32 arrays in 4-byte storage with native binary32 kernels.

The definition of every f32 operation is unchanged (the binary64 operation rounded once by `_ail_ta_r32`). The prelude
spells it out in the `_ail_tz_*` primitives (plain Python: CPython and the general path run them); the typed path calls
the C kernels of python/pkg-v12/f32rt.py instead. This module checks that the two give the same bits:

* identity (C): tools/f32_identity.c -- native + - * / sqrt and the double->float store against r32 of the binary64
  result, every special class, every binary32 for sqrt;
* primitives (CPython): `_ail_tz_get` / `_ail_tz_put` against `struct`, `_ail_tz_aa` / `_ail_tz_as` / `_ail_tz_un` against
  `struct`-rounded binary64 results;
* fuzz (native): array_f32_fuzz.py -- every result hashed through tobytes() -- built in the default build (vector
  kernels), with -DAILZ_SCALAR (scalar kernels) and with AIL_UNIFIED_FORCE=1 (the Python primitives compiled), each
  printing what CPython prints with the reference ail_array.py;
* refusals: a walk of an f32 array during which an array could change is refused by name.
"""
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
sys.path.insert(0, str(PKG))
import ailarray  # noqa: E402

CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
IDENTITY = ROOT.parent / "tools" / "f32_identity.c"
ROUNDS = 60


def prelude():
    ns = {}
    exec(compile((PKG / "prelude_ailarray.py").read_text(encoding="utf-8"), "prelude_ailarray.py", "exec"), ns)
    return ns


def f32(x):
    if x != x:
        return math.nan
    try:
        return struct.unpack("<f", struct.pack("<f", x))[0]
    except OverflowError:
        return math.copysign(math.inf, x)


def pat(x):
    return struct.pack("<f", x) if x == x else bytes.fromhex("0000c07f")


def fuzz_source():
    text = (ROOT / "array_f32_fuzz.py").read_text(encoding="utf-8")
    return text.replace("ROUNDS = 400", "ROUNDS = %d" % ROUNDS, 1)


def run_py(directory):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", "prog.py"], cwd=directory, capture_output=True, text=True, timeout=1800, env=env)


@unittest.skipUnless(CC and IDENTITY.exists(), "C compiler and tools/f32_identity.c required")
class Identity(unittest.TestCase):
    def test_native_binary32_equals_rounded_binary64(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "identity"
            subprocess.run([CC, "-O2", "-ffp-contract=off", "-o", str(exe), str(IDENTITY), "-lm"], check=True)
            done = subprocess.run([str(exe), "2000000"], capture_output=True, text=True, timeout=1200)
            self.assertEqual(done.returncode, 0, done.stdout[-2000:])
            self.assertIn("TOTAL mismatches 0", done.stdout)


class Primitives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = prelude()
        rng = random.Random(11)
        vals = [0.0, -0.0, math.inf, -math.inf, math.nan, 1.401298464324817e-45, 3.4028234663852886e+38, 1.0, 0.1]
        for _ in range(3000):
            u = rng.getrandbits(32)
            v = struct.unpack("<f", struct.pack("<I", u))[0]
            vals.append(math.nan if v != v else v)
        cls.vals = vals

    def test_put_get(self):
        put, get = self.ns["_ail_tz_put"], self.ns["_ail_tz_get"]
        rng = random.Random(12)
        xs = self.vals + [rng.uniform(-1, 1) * 2.0 ** rng.randint(-160, 130) for _ in range(3000)]
        b = bytearray(4 * len(xs))
        for k, x in enumerate(xs):
            put(b, k, x)
        for k, x in enumerate(xs):
            self.assertEqual(bytes(b[4 * k:4 * k + 4]), pat(f32(x)), repr(x))
            self.assertEqual(pat(get(b, k)), pat(f32(x)))

    def test_elementwise(self):
        ns = self.ns
        rng = random.Random(13)
        xs = self.vals[:]
        ys = self.vals[:]
        rng.shuffle(ys)
        n = len(xs)
        a, b, d = bytearray(4 * n), bytearray(4 * n), bytearray(4 * n)
        for k in range(n):
            ns["_ail_tz_put"](a, k, xs[k])
            ns["_ail_tz_put"](b, k, ys[k])

        def ref(op, x, y):
            if op == 0:
                return x + y
            if op == 1:
                return x - y
            if op == 2:
                return x * y
            if y == 0.0:
                return math.nan if x != x or x == 0.0 else math.copysign(math.inf, math.copysign(1.0, x) * math.copysign(1.0, y))
            return x / y
        for op in range(4):
            ns["_ail_tz_aa"](d, a, b, n, op)
            for k in range(n):
                self.assertEqual(bytes(d[4 * k:4 * k + 4]), pat(f32(ref(op, xs[k], ys[k]))), (op, xs[k], ys[k]))
            ns["_ail_tz_as"](d, a, 0.75, n, op, 1)
            for k in range(n):
                self.assertEqual(bytes(d[4 * k:4 * k + 4]), pat(f32(ref(op, 0.75, xs[k]))), (op, xs[k]))
        ns["_ail_tz_un"](d, a, n, 2)
        for k in range(n):
            x = xs[k]
            self.assertEqual(bytes(d[4 * k:4 * k + 4]), pat(f32(math.sqrt(x) if x == x and x >= 0.0 else math.nan)), x)


REFUSED = [
    ("enumerate store", "for i, v in enumerate(a):\n    a[i] = 1.0\n", "walked by enumerate"),
    ("zip in-place", "for u, v in zip(a, a):\n    a += 1.0\n", "walked by enumerate"),
    ("generator kept", "g = (v for v in a)\n", "not consumed at once"),
    ("enumerate kept", "e = enumerate(a)\n", "kept for later"),
    ("user call in comprehension", "def f(x: float) -> float:\n    return x\nprint([f(v) for v in a])\n", "comprehension"),
]


class Refusals(unittest.TestCase):
    def test_walks_that_can_change_an_array(self):
        for name, body, needle in REFUSED:
            with self.subTest(case=name):
                src = "import ail_array as ta\na = ta.zeros(3, ta.f32)\n" + body
                notes = []
                self.assertEqual(ailarray.rewrite_text(src, notes), src)
                self.assertTrue(notes)
                self.assertIn(needle, notes[0][1])
                self.assertIn("write instead", notes[0][1])

    def test_direct_loop_with_a_store_is_built(self):
        notes = []
        ailarray.rewrite_text("import ail_array as ta\na = ta.zeros(3, ta.f32)\nfor v in a:\n    a[0] = v + 1.0\n", notes)
        self.assertEqual(notes, [])


@unittest.skipUnless(CC, "installed C compiler required")
class Fuzz(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-array-f32native-")
        base = Path(cls.tmp.name)
        src = fuzz_source()
        ref = base / "ref"
        ref.mkdir()
        shutil.copy(ROOT / "ail_array.py", ref / "ail_array.py")
        (ref / "prog.py").write_text(src, encoding="utf-8")
        cls.ref = run_py(ref)
        low = base / "low"
        low.mkdir()
        notes = []
        (low / "prog.py").write_text(ailarray.rewrite_text(src, notes), encoding="utf-8")
        cls.notes = notes
        cls.low = run_py(low)
        cls.native = {}
        for mode in ("default", "scalar", "forced"):
            d = base / mode
            d.mkdir()
            (d / "prog.py").write_text(src, encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            for key in ("AIL_UNIFIED_FORCE", "AIL_NO_GENERAL", "AIL_EXTRA_CFLAGS"):
                env.pop(key, None)
            if mode == "forced":
                env["AIL_UNIFIED_FORCE"] = "1"
            if mode == "scalar":
                env["AIL_EXTRA_CFLAGS"] = "-DAILZ_SCALAR"
            done = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", "prog.py", "-o", "prog.out",
                                   "--no-cache"], cwd=d, capture_output=True, text=True, timeout=1800, env=env)
            run = None
            if done.returncode == 0:
                run = subprocess.run([str(d / "prog.out")], capture_output=True, text=True, timeout=1800)
            cls.native[mode] = (done, run)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_reference_and_lowered_text(self):
        self.assertEqual(self.ref.returncode, 0, self.ref.stderr[-800:])
        self.assertEqual(self.notes, [])
        self.assertEqual(self.low.stdout, self.ref.stdout)
        self.assertIn("element operations:", self.ref.stdout)

    def check(self, mode):
        done, run = self.native[mode]
        self.assertEqual(done.returncode, 0, (done.stdout + done.stderr)[-1500:])
        self.assertEqual(run.returncode, 0, run.stderr[-800:])
        self.assertEqual(run.stdout, self.ref.stdout)

    def test_default_build(self):
        self.check("default")
        self.assertNotIn("general path", self.native["default"][0].stderr)

    def test_scalar_kernels(self):
        self.check("scalar")

    def test_forced_general_path(self):
        self.check("forced")


if __name__ == "__main__":
    unittest.main()
