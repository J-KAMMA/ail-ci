"""Job aicore1 (docs/design/TYPED_ARRAY.md 3.9): what an MLP forward pass and an attention block need from `ail_array`.

* broadcasting when one operand is 2-D (NumPy's rule on 1-D / 2-D: a 1-D array is a row, a dimension of 1 repeats);
* reductions along an axis (`ta.sum / min / max` with `axis=` and `keepdims=`, `ta.argmin / argmax` with `axis=`), each
  row or column reduced by the 1-D function, so the fixed order of 3.5 holds per row;
* element-wise operations on 2-D f32 arrays.

reference (CPython only): the rules against independent code; white box: the lowered text, run by CPython, prints what the
reference prints; native: array_ai_cases/*.py built (default build, AIL_UNIFIED_FORCE=1, typed path alone) print the
reference's bytes; refusals: what stays unbuilt is refused with file:line and `write instead:`.
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
import ail_array as ta  # noqa: E402
import ailarray  # noqa: E402

CASES = ROOT / "array_ai_cases"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
NAMES = sorted(p.stem for p in CASES.glob("*.py"))
# The typed path alone (AIL_NO_GENERAL=1) has no `except TypeError` and does not build the always-raising 2-D helpers
# (`_ail_tam_te`: "raise requires a built-in exception value"); both were so before this job (a `ta.matmul` dtype mismatch
# fails the same way). The default and forced builds run them.
NOT_TYPED = {"bdtype"}


def bits(x):
    return struct.pack("<d", x)


def run_py(directory, name):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", name], cwd=directory, capture_output=True, text=True, timeout=600, env=env)


def lowered(source):
    notes = []
    out = ailarray.rewrite_text(source, notes)
    return out, notes


def rand_rows(rng, r, c):
    return [[rng.uniform(-5.0, 5.0) for _ in range(c)] for _ in range(r)]


class Reference(unittest.TestCase):
    def test_broadcast_equals_the_loop_over_elements(self):
        rng = random.Random(5)
        for dt in (ta.f64, ta.f32):
            m = ta.array(rand_rows(rng, 3, 4), dt)
            row = ta.array([rng.uniform(-2, 2) for _ in range(4)], dt)
            col = ta.array([[0.5], [-0.0], [3.0]], dt)
            for name, fn in (("+", lambda x, y: x + y), ("-", lambda x, y: x - y), ("*", lambda x, y: x * y),
                             ("/", lambda x, y: x / y)):
                got = fn(m, row)
                self.assertEqual(got.shape, (3, 4))
                for i in range(3):
                    self.assertEqual(fn(m[i], row).tobytes(), got[i].tobytes(), (dt, name))
                got = fn(row, m)
                for i in range(3):
                    self.assertEqual(fn(row, m[i]).tobytes(), got[i].tobytes(), (dt, name))
                got = fn(m, col)
                for i in range(3):
                    self.assertEqual(fn(m[i], col[i, 0]).tobytes(), got[i].tobytes(), (dt, name))
            outer = col * ta.array([[1.0, 2.0]], dt)
            self.assertEqual(outer.tolist(), [[0.5, 1.0], [-0.0, -0.0], [3.0, 6.0]])
            self.assertEqual(ta.maximum(m, row).tobytes(), ta.maximum(m, row * 1.0).tobytes())
            self.assertEqual(ta.minimum(row, m).shape, (3, 4))

    def test_broadcast_in_place_and_errors(self):
        m = ta.zeros((2, 3), ta.f64)
        m += ta.array([1.0, 2.0, 3.0], ta.f64)
        m *= ta.array([[2.0], [-1.0]], ta.f64)
        self.assertEqual(m.tolist(), [[2.0, 4.0, 6.0], [-1.0, -2.0, -3.0]])
        cases = [
            (lambda: m + ta.zeros(4, ta.f64), ValueError, "ail_array: shapes differ: (2, 3) and (4,)"),
            (lambda: ta.zeros(5, ta.f64) - m, ValueError, "ail_array: shapes differ: (5,) and (2, 3)"),
            (lambda: m * ta.zeros((3, 1), ta.f64), ValueError, "ail_array: shapes differ: (2, 3) and (3, 1)"),
            (lambda: m + ta.zeros(3, ta.f32), TypeError,
             "ail_array: f64 + f32: dtypes differ; write a.astype(ta.f32) or b.astype(ta.f64)"),
            (lambda: ta.maximum(m, ta.zeros(2, ta.f64)), ValueError, "ail_array: shapes differ: (2, 3) and (2,)"),
        ]
        for fn, exc, text in cases:
            with self.subTest(text=text):
                with self.assertRaises(exc) as ctx:
                    fn()
                self.assertEqual(str(ctx.exception), text)
        c = ta.zeros((2, 1), ta.f64)
        with self.assertRaisesRegex(ValueError, r"^ail_array: shapes differ: \(2, 1\) and \(2, 3\)$"):
            c += m
        v = ta.zeros(3, ta.f64)
        with self.assertRaisesRegex(ValueError, r"^ail_array: shapes differ: \(3,\) and \(2, 3\)$"):
            v += m
        # two 1-D arrays still need the same length
        with self.assertRaisesRegex(ValueError, r"^ail_array: shapes differ: \(3,\) and \(1,\)$"):
            ta.zeros(3, ta.f64) + ta.zeros(1, ta.f64)

    def test_axis_reductions_are_the_one_d_reductions(self):
        rng = random.Random(9)
        for dt in (ta.f64, ta.f32):
            for c in (1, 15, 16, 17, 1025):
                rows = rand_rows(rng, 3, c)
                rows[1][c // 2] = math.inf
                m = ta.array(rows, dt)
                s = ta.sum(m, axis=1)
                self.assertEqual(s.dtype, dt)
                for i in range(3):
                    self.assertEqual(bits(s[i]), bits(ta.sum(m[i])))
                    self.assertEqual(bits(ta.max(m, axis=-1)[i]), bits(ta.max(m[i])))
                    self.assertEqual(bits(ta.min(m, axis=1)[i]), bits(ta.min(m[i])))
                    self.assertEqual(ta.argmax(m, axis=1)[i], ta.argmax(m[i]))
                cols = ta.sum(m, axis=0)
                for j in range(c):
                    col = ta.array([rows[i][j] for i in range(3)], dt)
                    self.assertEqual(bits(cols[j]), bits(ta.sum(col)))
                    self.assertEqual(ta.argmin(m, axis=-2)[j], ta.argmin(col))
                self.assertEqual(ta.sum(m, axis=1, keepdims=True).shape, (3, 1))
                self.assertEqual(ta.max(m, axis=0, keepdims=True).shape, (1, c))
        self.assertEqual(ta.sum(ta.zeros((2, 3), ta.f16), axis=1).dtype, ta.f32)
        self.assertEqual(ta.argmax(ta.zeros((2, 3), ta.f32), axis=1).dtype, ta.int32)
        self.assertEqual(ta.sum(ta.zeros((0, 3), ta.f64), axis=1).shape, (0,))
        self.assertEqual(ta.sum(ta.zeros((2, 0), ta.f64), axis=1).tolist(), [0.0, 0.0])

    def test_axis_errors(self):
        m = ta.zeros((2, 3), ta.f64)
        cases = [
            (lambda: ta.sum(ta.zeros(3, ta.f64), axis=0), ValueError,
             "ail_array.sum(): axis= needs a 2-D array; reduce a 1-D array with ta.sum(a)"),
            (lambda: ta.sum(m, axis=2), ValueError, "ail_array.sum(): axis must be 0 or 1 (or -2, -1), not 2"),
            (lambda: ta.max(m, axis=True), ValueError, "ail_array.max(): axis must be 0 or 1 (or -2, -1), not True"),
            (lambda: ta.sum(m, axis=1, keepdims=1), TypeError, "ail_array.sum(): keepdims must be True or False, not int"),
            (lambda: ta.sum(ta.zeros((2, 3), ta.int32), axis=1), TypeError,
             "ail_array.sum(axis=...) is built for float arrays, not int32"),
            (lambda: ta.sum(m, acc=ta.f64, axis=1), ValueError,
             "ail_array.sum(): acc= and order= are not built together with axis="),
            (lambda: ta.max(ta.zeros((2, 0), ta.f64), axis=1), ValueError, "max() iterable argument is empty"),
            (lambda: ta.sum(m), ValueError, "ail_array.sum(): 2-D arrays are not built here; reduce one row: ta.sum(M[i])"),
        ]
        for fn, exc, text in cases:
            with self.subTest(text=text):
                with self.assertRaises(exc) as ctx:
                    fn()
                self.assertEqual(str(ctx.exception), text)

    def test_softmax_rows(self):
        s = ta.array([[1.0, 2.0, 3.0], [1000.0, 1000.0, -math.inf]], ta.f32)
        e = ta.exp(s - ta.max(s, axis=1, keepdims=True))
        p = e / ta.sum(e, axis=1, keepdims=True)
        self.assertEqual(p.shape, (2, 3))
        self.assertEqual(p[1].tolist(), [0.5, 0.5, 0.0])


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
                (tmp / "low").mkdir()
                (tmp / "low" / "prog.py").write_text(text, encoding="utf-8")
                ref = run_py(tmp / "ref", "prog.py")
                low = run_py(tmp / "low", "prog.py")
                self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
                self.assertEqual(low.stdout, ref.stdout)
                self.assertEqual(low.returncode, ref.returncode)


REFUSED = [
    ("axis of 1-D", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = ta.sum(a, axis=0)\n", "of a 1-D array"),
    ("axis not literal", "import ail_array as ta\nk = 1\na = ta.zeros((2, 3), ta.f64)\nb = ta.sum(a, axis=k)\n",
     "literal 0 or 1"),
    ("axis 2", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = ta.max(a, axis=2)\n", "literal 0 or 1"),
    ("keepdims not literal", "import ail_array as ta\nk = True\na = ta.zeros((2, 3), ta.f64)\nb = ta.sum(a, axis=1, keepdims=k)\n",
     "keepdims"),
    ("acc with axis", "import ail_array as ta\na = ta.zeros((2, 3), ta.f32)\nb = ta.sum(a, acc=ta.f64, axis=1)\n",
     "acc= or order= together with axis="),
    ("int32 axis", "import ail_array as ta\na = ta.zeros((2, 3), ta.int32)\nb = ta.sum(a, axis=1)\n", "int32"),
    ("argmax keepdims", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = ta.argmax(a, axis=1, keepdims=True)\n",
     "not a parameter"),
    ("int32 2-D element-wise", "import ail_array as ta\na = ta.zeros((2, 3), ta.int32)\nb = a + a\n", "not built"),
    ("1-D in place with 2-D f32", "import ail_array as ta\na = ta.zeros((2, 3), ta.f32)\nb = ta.zeros(3, ta.f32)\nb *= a\n",
     "in-place operator with a 1-D array"),
    ("pick of 2-D and 1-D of another dtype", "import ail_array as ta\na = ta.zeros((2, 3), ta.f32)\n"
     "b = ta.minimum(a, ta.zeros(3, ta.f64))\n", "another dtype"),
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
                self.assertIn("write instead", why)


@unittest.skipUnless(CC, "installed C compiler required")
class Native(unittest.TestCase):
    """Built programs print what CPython prints with the reference beside the program."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-array-aicore1-")
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
                                  cwd=d, capture_output=True, text=True, timeout=1800, env=env)
            run = None
            if done.returncode == 0:
                run = subprocess.run([str(d / "prog.out")], capture_output=True, text=True, timeout=600)
            return job, done, run

        jobs = [(n, m) for n in NAMES for m in ("default", "forced", "typed") if not (m == "typed" and n in NOT_TYPED)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            cls.out = dict(pool.map(lambda j: (j, build(j)), jobs))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, name, mode):
        job, done, run = self.out[(name, mode)]
        self.assertEqual(done.returncode, 0, (done.stdout + done.stderr)[-1500:])
        ref = self.ref[name]
        self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
        self.assertEqual(run.stdout, ref.stdout)
        self.assertEqual(run.returncode, ref.returncode)


def _add(name, mode):
    setattr(Native, "test_%s_%s" % (name, mode), lambda self: self.check(name, mode))


for _n in NAMES:
    for _m in ("default", "forced", "typed"):
        if not (_m == "typed" and _n in NOT_TYPED):
            _add(_n, _m)


if __name__ == "__main__":
    unittest.main()
