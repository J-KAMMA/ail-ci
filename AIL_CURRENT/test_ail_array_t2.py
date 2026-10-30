"""Stage T2 of docs/design/TYPED_ARRAY.md: `import ail_array` for f64 and int32, lowered by python/pkg-v12/ailarray.py.

* white box (CPython only): the lowered program text, run by CPython with no `ail_array.py` beside it, prints what the
  reference `ail_array.py` prints for the original program (stdout and exit code);
* native: the same programs built by the compiler (default build and AIL_UNIFIED_FORCE=1) print the same bytes as CPython
  with the reference (array_t2_cases/*.py: elementwise ops, indexing and slices, int32 overflow and zero division, the
  fixed sum/dot order at the lane and block boundaries, inf/nan/-0.0, error texts);
* prelude: the bits of a double made with exact float arithmetic equal `struct`;
* refusals: each unsupported construct is refused with file:line and `write instead:`; a program without the import is
  returned untouched.
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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PKG))
import ailarray  # noqa: E402
import prelude_ailarray as P  # noqa: E402

CASES = ROOT / "array_t2_cases"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
NAMES = sorted(p.stem for p in CASES.glob("*.py"))


def run_py(directory, name):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", name], cwd=directory, capture_output=True, text=True, timeout=300, env=env)


def lowered(source):
    notes = []
    out = ailarray.rewrite_text(source, notes)
    return out, notes


class WhiteBox(unittest.TestCase):
    def test_cases_lowered_text_equals_reference(self):
        for name in NAMES:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                source = (CASES / (name + ".py")).read_text(encoding="utf-8")
                (tmp / "ref").mkdir()
                shutil.copy(ROOT / "ail_array.py", tmp / "ref" / "ail_array.py")
                (tmp / "ref" / "prog.py").write_text(source, encoding="utf-8")
                text, notes = lowered(source)
                self.assertEqual(notes, [])
                self.assertNotEqual(text, source)
                self.assertNotIn("import ail_array", text)
                (tmp / "low").mkdir()
                (tmp / "low" / "prog.py").write_text(text, encoding="utf-8")
                ref = run_py(tmp / "ref", "prog.py")
                low = run_py(tmp / "low", "prog.py")
                self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
                self.assertEqual(low.stdout, ref.stdout)
                self.assertEqual(low.returncode, ref.returncode)

    def test_program_without_the_import_is_returned_untouched(self):
        for src in ("print(1)\n", "x = 'ail_array'\nprint(x)\n", "import math\nprint(math.pi)\n"):
            self.assertIs(ailarray.rewrite_text(src, []), src)

    def test_noncanonical_nan_is_a_loud_stop(self):
        src = ("import ail_array as ta\n\ndef main():\n"
               "    a = ta.frombytes(bytes([1, 0, 0, 0, 0, 0, 240, 127]), ta.f64)\n    print(a)\n\nmain()\n")
        text, notes = lowered(src)
        self.assertEqual(notes, [])
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "p.py").write_text(text, encoding="utf-8")
            done = run_py(tmp, "p.py")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("NaN", done.stderr)


class PreludeBits(unittest.TestCase):
    def test_bits_and_back_equal_struct(self):
        rng = random.Random(7)
        values = [0.0, -0.0, 1.0, 5e-324, -5e-324, 2.2250738585072014e-308, 2.225073858507201e-308,
                  1.7976931348623157e308, math.inf, -math.inf, 0.1, 1.0000000000000002]
        for _ in range(20000):
            b = rng.getrandbits(64)
            if rng.random() < 0.3:
                b = (b & ~(0x7ff << 52)) | (rng.choice([0, 1, 2, 1022, 1023, 1024, 2046]) << 52)
            values.append(struct.unpack("<d", struct.pack("<Q", b))[0])
        for x in values:
            if x != x:
                continue
            hi, lo = P._ail_ta_bits(x)
            want = struct.unpack("<Q", struct.pack("<d", x))[0]
            self.assertEqual((hi << 32) | lo, want, repr(x))
            self.assertEqual(struct.pack("<d", P._ail_ta_unbits(hi, lo)), struct.pack("<d", x), repr(x))

    def test_every_exponent(self):
        for e in range(-1074, 1024):
            x = math.ldexp(1.0, e)
            hi, lo = P._ail_ta_bits(x)
            self.assertEqual((hi << 32) | lo, struct.unpack("<Q", struct.pack("<d", x))[0], e)
            y = math.nextafter(x, 0.0) if e > -1074 else 0.0
            hi, lo = P._ail_ta_bits(y)
            self.assertEqual((hi << 32) | lo, struct.unpack("<Q", struct.pack("<d", y))[0], e)

    def test_slice_indices_equal_python(self):
        for n in range(0, 8):
            for lo in range(-10, 11):
                for hi in range(-10, 11):
                    for st in (1, 2, 3, -1, -2, -5):
                        for flags in range(8):
                            if flags & 4 == 0 and st != 1:
                                continue
                            sl = slice(lo if flags & 1 else None, hi if flags & 2 else None, st if flags & 4 else None)
                            got = P._ail_ta_slice(n, lo, hi, st, flags)
                            want = range(*sl.indices(n))
                            self.assertEqual((got[1], got[0] if got[1] else 0, got[2] if got[1] else 0),
                                             (len(want), want.start if len(want) else 0, want.step if len(want) else 0))


REFUSED = [
    ("f32", "import ail_array as ta\na = ta.zeros(3, ta.f32)\n", "stage T3"),
    ("f16", "import ail_array as ta\na = ta.array([1.0], ta.f16)\n", "stage T3"),
    ("int8", "import ail_array as ta\na = ta.zeros(3, ta.int8)\n", "stage T3"),
    ("int64", "import ail_array as ta\na = ta.zeros(3, ta.int64)\n", "has f64, f32, f16, int8, int32"),
    ("bf16", "import ail_array as ta\na = ta.zeros(3, ta.bf16)\n", "has f64, f32, f16, int8, int32"),
    ("dtype not literal", "import ail_array as ta\ndt = ta.f64\na = ta.zeros(3, dt)\n", "write instead"),
    ("append", "import ail_array as ta\na = ta.zeros(3, ta.f64)\na.append(1.0)\n", "fixed length"),
    ("pop", "import ail_array as ta\na = ta.zeros(3, ta.f64)\na.pop()\n", "fixed length"),
    ("memoryview", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nm = memoryview(a)\n", "memoryview"),
    ("less", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a < a\n", "write instead"),
    ("mask", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a[a > 0.0]\n", "write instead"),
    ("fancy", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a[[0, 2]]\n", "write instead"),
    ("pow", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a ** 2\n", "write instead"),
    ("float floordiv", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a // 2\n", "write instead"),
    ("float mod", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a % 2\n", "write instead"),
    ("int truediv", "import ail_array as ta\na = ta.zeros(3, ta.int32)\nb = a / 2\n", "astype"),
    ("bitand", "import ail_array as ta\na = ta.zeros(3, ta.int32)\nb = a & a\n", "write instead"),
    ("shift", "import ail_array as ta\na = ta.zeros(3, ta.int32)\nb = a << 1\n", "write instead"),
    ("matmul", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a @ a\n", "T6"),
    ("2-D", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\n", "write instead"),
    ("3-D", "import ail_array as ta\na = ta.zeros((2, 3, 4), ta.f64)\n", "write instead"),
    ("2-D index", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a[1, 2]\n", "write instead"),
    ("shape", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a.shape\n", "len(a)"),
    ("dtype attr", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a.dtype\n", "write instead"),
    ("order min", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = ta.min(a, order='any')\n", "inexact"),
    ("in", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = 1.0 in a\n", "write instead"),
    ("truth", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nif a:\n    pass\n", "len(a) > 0"),
    ("param dtypes", "import ail_array as ta\ndef f(a):\n    return a\nf(ta.zeros(1, ta.f64))\nf(ta.zeros(1, ta.int32))\n",
     "annotate"),
    ("unknown operand", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = a + mystery()\n",
     "annotate"),
    ("bare Array annotation", "import ail_array as ta\ndef f(a: ta.Array):\n    return 1\n", "ta.Array[ta.f64]"),
    ("numeric list of unknown elements", "import ail_array as ta\ndef f(xs):\n    return ta.array(xs, ta.f64)\n", "write instead"),
    ("builtin on array", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = tuple(a)\n", "write instead"),
    ("del", "import ail_array as ta\na = ta.zeros(3, ta.f64)\ndel a[0]\n", "write instead"),
    ("star import", "from ail_array import *\n", "name what you use"),
    ("print hazard", "import ail_array as ta\ndef bump(a: ta.Array[ta.f64]) -> ta.Array[ta.f64]:\n    return a\n"
     "a = ta.zeros(3, ta.f64)\nx = [print(a, bump(a))]\n", "bind the arguments"),
]


class Refusals(unittest.TestCase):
    def test_each_refusal_has_a_line_and_a_hint(self):
        for name, src, needle in REFUSED:
            with self.subTest(case=name):
                text, notes = lowered(src)
                self.assertEqual(text, src, "a refused program is left as written")
                self.assertTrue(notes, "no refusal for %s" % name)
                line, why = notes[0]
                self.assertGreaterEqual(line, 1)
                self.assertIn(needle, why)

    def test_refused_program_without_the_refused_line_builds_text(self):
        text, notes = lowered("import ail_array as ta\na = ta.zeros(3, ta.f64)\nprint(a)\n")
        self.assertEqual(notes, [])
        self.assertIn("_ail_taf_zeros", text)

    @unittest.skipUnless(CC, "installed C compiler required")
    def test_cli_refusal_names_file_line_and_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "r.py").write_text("import ail_array as ta\n\ndef main():\n    a = ta.zeros(3, ta.f32)\n    print(a)\n\nmain()\n")
            done = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", "r.py", "-o", "r.out"],
                                  cwd=tmp, capture_output=True, text=True, timeout=300)
        self.assertNotEqual(done.returncode, 0)
        out = done.stdout + done.stderr
        self.assertIn("r.py:4", out)
        self.assertIn("write instead", out)


@unittest.skipUnless(CC, "installed C compiler required")
class Native(unittest.TestCase):
    """Built programs print what CPython prints with the reference beside the program."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-array-t2-")
        cls.dir = Path(cls.tmp.name)
        cls.ref = {}
        for name in NAMES:
            d = cls.dir / name / "ref"
            d.mkdir(parents=True)
            shutil.copy(ROOT / "ail_array.py", d)
            shutil.copy(CASES / (name + ".py"), d / "prog.py")
            cls.ref[name] = run_py(d, "prog.py")

        def build(job):
            name, mode = job
            d = cls.dir / name / mode
            d.mkdir(parents=True)
            shutil.copy(CASES / (name + ".py"), d / "prog.py")
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            for key in ("AIL_UNIFIED_FORCE", "AIL_NO_GENERAL"):
                env.pop(key, None)
            if mode == "forced":
                env["AIL_UNIFIED_FORCE"] = "1"
            if mode == "typed":
                env["AIL_NO_GENERAL"] = "1"
            done = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", "prog.py", "-o", "prog.out"],
                                  cwd=d, capture_output=True, text=True, timeout=900, env=env)
            run = None
            if done.returncode == 0:
                run = subprocess.run([str(d / "prog.out")], capture_output=True, text=True, timeout=300)
            return job, done, run

        jobs = [(n, m) for n in NAMES for m in ("default", "forced")] + [(n, "typed") for n in ("f64ops", "int32")
                                                                         if n in NAMES]
        with ThreadPoolExecutor(max_workers=2) as pool:
            cls.out = dict(pool.map(lambda j: (j, build(j)), jobs))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, name, mode):
        job, done, run = self.out[(name, mode)][0], self.out[(name, mode)][1], self.out[(name, mode)][2]
        self.assertEqual(done.returncode, 0, (done.stdout + done.stderr)[-1500:])
        ref = self.ref[name]
        self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
        self.assertEqual(run.stdout, ref.stdout)
        self.assertEqual(run.returncode, ref.returncode)


def _add(name, mode):
    setattr(Native, "test_%s_%s" % (name, mode), lambda self: self.check(name, mode))


for _n in NAMES:
    for _m in ("default", "forced"):
        _add(_n, _m)
for _n in ("f64ops", "int32"):
    if _n in NAMES:
        _add(_n, "typed")


if __name__ == "__main__":
    unittest.main()
