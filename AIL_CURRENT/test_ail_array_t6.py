"""Stage T6 of docs/design/TYPED_ARRAY.md: 2-D f64 arrays and `ta.matmul` (reference, lowering, native build).

* reference (CPython only): shapes, `[i, j]` indexing, row slices, `.T`, element-wise rules on 2-D arrays, the exact error
  texts, and `matmul` against an independent implementation of the fixed order (design 3.5 / 3.7): every output element equals
  `ta.dot(row, column)` bit for bit, at the lane and block boundaries and with specials planted;
* white box: the lowered program text, run by CPython with no `ail_array.py` beside it, prints what the reference prints;
* native: the same programs built by the compiler (default build, AIL_UNIFIED_FORCE=1, and the typed path alone) print the same
  bytes as CPython with the reference (array_t6_cases/*.py);
* refusals: each 2-D construct that is not built is refused with file:line and `write instead:`.
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

CASES = ROOT / "array_t6_cases"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
NAMES = sorted(p.stem for p in CASES.glob("*.py"))
SPECIALS = [math.inf, -math.inf, math.nan, -0.0, 0.0, 1e308, -1e308, 5e-324, 2.2250738585072014e-308, 1e-200]


def bits(x):
    return struct.pack("<d", x)


def order_sum(products):
    """The fixed order of design 3.5, written independently of ail_array.py: 16 lanes from -0.0 in blocks of 1024, the 8-4-2-1
    tree, a power-of-two tree over the blocks; the empty sum is +0.0 and a NaN result is the canonical one."""
    if not products:
        return 0.0
    blocks = []
    for s in range(0, len(products), 1024):
        chunk = products[s:s + 1024]
        lane = [-0.0] * 16
        for k, p in enumerate(chunk):
            lane[k % 16] = lane[k % 16] + p
        for w in (8, 4, 2, 1):
            for i in range(w):
                lane[i] = lane[i] + lane[i + w]
        blocks.append(lane[0])

    def tree(lo, hi):
        if hi - lo == 1:
            return blocks[lo]
        p = 1
        while p * 2 < hi - lo:
            p *= 2
        return tree(lo, lo + p) + tree(lo + p, hi)

    r = tree(0, len(blocks))
    return math.nan if r != r else r


def matrix(rows):
    return ta.array(rows, ta.f64)


def random_matrix(rng, r, c, specials=False):
    rows = [[rng.uniform(-3.0, 3.0) for _ in range(c)] for _ in range(r)]
    if specials and r and c:
        for _ in range(3):
            rows[rng.randrange(r)][rng.randrange(c)] = rng.choice(SPECIALS)
    return rows


def run_py(directory, name):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", name], cwd=directory, capture_output=True, text=True, timeout=600, env=env)


def lowered(source):
    notes = []
    out = ailarray.rewrite_text(source, notes)
    return out, notes


class Reference(unittest.TestCase):
    def test_shape_indexing_and_slices(self):
        a = matrix([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        self.assertEqual(a.shape, (2, 3))
        self.assertEqual(len(a), 2)
        self.assertEqual(a[1, 2], 6.0)
        self.assertEqual(a[-1, -3], 4.0)
        self.assertEqual(a[1].tolist(), [4.0, 5.0, 6.0])
        self.assertEqual(a[1].shape, (3,))
        self.assertEqual(a[1:].shape, (1, 3))
        self.assertEqual(a[::-1].tolist(), [[4.0, 5.0, 6.0], [1.0, 2.0, 3.0]])
        self.assertEqual(a[5:].shape, (0, 3))
        self.assertEqual(a.T.shape, (3, 2))
        self.assertEqual(a.T.tolist(), [[1.0, 4.0], [2.0, 5.0], [3.0, 6.0]])
        self.assertEqual(a.T.T, a)
        self.assertEqual(repr(a), "array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], f64)")
        self.assertEqual(a.tobytes(), b"".join(bits(x) for x in (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)))
        b = a.copy()
        b[0, 0] = 9.0
        b[1] = ta.array([7.0, 8.0, -0.0], ta.f64)
        self.assertEqual(a[0, 0], 1.0)
        self.assertEqual(b.tolist(), [[9.0, 2.0, 3.0], [7.0, 8.0, -0.0]])
        self.assertNotEqual(a, b)
        self.assertEqual(a, a.copy())
        self.assertNotEqual(a, ta.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], ta.f64))
        z = ta.zeros((0, 3), ta.f64)
        self.assertEqual((z.shape, len(z), z.T.shape, z.tolist()), ((0, 3), 0, (3, 0), []))
        self.assertEqual(ta.zeros((3, 0), ta.f64).tolist(), [[], [], []])
        self.assertEqual(ta.zeros((2, 2), ta.int32).tolist(), [[0, 0], [0, 0]])
        self.assertEqual(ta.zeros((1, 3), ta.f64).shape, (1, 3))
        self.assertEqual(ta.zeros((4,), ta.f64).shape, (4,))
        self.assertEqual(ta.full((2, 2), 3, ta.f64).tolist(), [[3.0, 3.0], [3.0, 3.0]])

    def test_elementwise_rules(self):
        a = matrix([[1.0, -2.0], [0.5, 4.0]])
        b = matrix([[2.0, 2.0], [2.0, 2.0]])
        self.assertEqual((a + b).tolist(), [[3.0, 0.0], [2.5, 6.0]])
        self.assertEqual((a * 2.0).shape, (2, 2))
        self.assertEqual((2.0 - a).tolist(), [[1.0, 4.0], [1.5, -2.0]])
        self.assertEqual((-a).tolist(), [[-1.0, 2.0], [-0.5, -4.0]])
        self.assertEqual(abs(a).tolist(), [[1.0, 2.0], [0.5, 4.0]])
        self.assertEqual(ta.sqrt(abs(a)).shape, (2, 2))
        self.assertEqual(ta.maximum(a, 1.0).tolist(), [[1.0, 1.0], [1.0, 4.0]])
        self.assertEqual(ta.clip(a, 0.0, 2.0).tolist(), [[1.0, 0.0], [0.5, 2.0]])
        c = a.copy()
        c += b
        c /= 4.0
        self.assertEqual(c.tolist(), [[0.75, 0.0], [0.625, 1.5]])
        self.assertEqual(a.astype(ta.f32).shape, (2, 2))
        self.assertEqual((a / 0.0).tolist()[0][0], math.inf)
        d = ta.array([[0.0, -0.0]], ta.f64) / ta.array([[0.0, 0.0]], ta.f64)
        self.assertEqual(d.tobytes(), bits(math.nan) * 2)

    def test_error_texts(self):
        a = ta.zeros((2, 3), ta.f64)
        b = ta.zeros((4, 5), ta.f64)
        cases = [
            (lambda: a + b, ValueError, "ail_array: shapes differ: (2, 3) and (4, 5)"),
            (lambda: a + ta.zeros(3, ta.f64), ValueError, "ail_array: shapes differ: (2, 3) and (3,)"),
            (lambda: ta.zeros(6, ta.f64) + a, ValueError, "ail_array: shapes differ: (6,) and (2, 3)"),
            (lambda: ta.matmul(a, b), ValueError, "ail_array: matmul: shapes (2, 3) and (4, 5) do not match: 3 != 4"),
            (lambda: ta.matmul(a, a), ValueError, "ail_array: matmul: shapes (2, 3) and (2, 3) do not match: 3 != 2"),
            (lambda: ta.matmul(ta.zeros(3, ta.f64), a), ValueError,
             "ail_array.matmul(): needs two 2-D arrays, not shapes (3,) and (2, 3)"),
            (lambda: ta.matmul(a, ta.zeros(2, ta.f64)), ValueError,
             "ail_array.matmul(): needs two 2-D arrays, not shapes (2, 3) and (2,)"),
            (lambda: ta.matmul(a, ta.zeros((3, 2), ta.f32)), TypeError,
             "ail_array: f64 matmul f32: dtypes differ; write a.astype(ta.f32) or b.astype(ta.f64)"),
            (lambda: ta.matmul(ta.zeros((2, 2), ta.f32), ta.zeros((2, 2), ta.f32)), TypeError,
             "ail_array.matmul(): only f64 arrays are built in this version, not f32"),
            (lambda: ta.matmul(a, [[1.0]]), TypeError, "ail_array.matmul() needs two ail_array.Array values"),
            (lambda: a[2, 0], IndexError, "array index out of range"),
            (lambda: a[0, -4], IndexError, "array index out of range"),
            (lambda: a[2], IndexError, "array index out of range"),
            (lambda: a[0, 1.5], TypeError, "array indices must be integers"),
            (lambda: a[0, 1:2], TypeError, "ail_array: a 2-D array takes M[i, j] (two ints), M[i] or M[a:b]"),
            (lambda: a[0, 0, 0], TypeError, "ail_array: a 2-D array takes M[i, j] (two ints), M[i] or M[a:b]"),
            (lambda: ta.zeros(3, ta.f64)[0, 0], TypeError, "ail_array: a 1-D array takes one index"),
            (lambda: ta.zeros((-1, 2), ta.f64), ValueError, "ail_array: negative length -1"),
            (lambda: ta.zeros((2, -2), ta.f64), ValueError, "ail_array: negative length -2"),
            (lambda: ta.zeros((2, 3, 4), ta.f64), ValueError, "ail_array has 1-D and 2-D arrays; shape (2, 3, 4)"),
            (lambda: ta.zeros((2, 1.5), ta.f64), TypeError, "ail_array: a length must be an int, not float"),
            (lambda: ta.array([[1.0, 2.0], [3.0]], ta.f64), ValueError, "ail_array: array(): rows differ in length (2 and 1)"),
            (lambda: ta.sum(a), ValueError, "ail_array.sum(): 2-D arrays are not built here; reduce one row: ta.sum(M[i])"),
            (lambda: ta.dot(a, a), ValueError, "ail_array.dot(): 2-D arrays are not built here; reduce one row: ta.dot(M[i])"),
            (lambda: ta.min(a), ValueError, "ail_array.min(): 2-D arrays are not built here; reduce one row: ta.min(M[i])"),
            (lambda: ta.zeros(3, ta.f64).T, ValueError, "ail_array: .T needs a 2-D array, not a 1-D one"),
        ]
        for fn, exc, text in cases:
            with self.subTest(text=text):
                with self.assertRaises(exc) as ctx:
                    fn()
                self.assertEqual(str(ctx.exception), text)
        with self.assertRaisesRegex(ValueError, "row assignment needs a 1-D array of 3 elements, not shape \\(4,\\)"):
            a[0] = ta.zeros(4, ta.f64)
        with self.assertRaises(IndexError):
            a[7] = ta.zeros(3, ta.f64)
        with self.assertRaisesRegex(TypeError, "slice assignment into a 2-D array is not built"):
            a[0:1] = a

    def test_matmul_small_by_hand(self):
        a = matrix([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        b = matrix([[1.0, 0.5], [2.0, 0.25], [3.0, -1.0]])
        c = ta.matmul(a, b)
        self.assertEqual((c.shape, c.tolist()), ((2, 2), [[14.0, -2.0], [32.0, -2.75]]))
        self.assertEqual(ta.matmul(ta.zeros((2, 0), ta.f64), ta.zeros((0, 3), ta.f64)).tobytes(), bits(0.0) * 6)
        self.assertEqual(ta.matmul(ta.zeros((0, 4), ta.f64), ta.zeros((4, 3), ta.f64)).shape, (0, 3))
        self.assertEqual(ta.matmul(ta.zeros((3, 4), ta.f64), ta.zeros((4, 0), ta.f64)).shape, (3, 0))
        self.assertEqual(ta.matmul(ta.zeros((0, 0), ta.f64), ta.zeros((0, 0), ta.f64)).shape, (0, 0))
        # -0.0 * 0.0 summed over lanes that start at -0.0: the sum of one -0.0 is -0.0
        self.assertEqual(ta.matmul(matrix([[-0.0]]), matrix([[0.0]])).tobytes(), bits(-0.0))
        self.assertEqual(ta.matmul(matrix([[-0.0]]), matrix([[-0.0]])).tobytes(), bits(0.0))

    def test_every_element_is_the_dot_of_its_row_and_column(self):
        rng = random.Random(2026)
        for m, k, n in [(1, 1, 1), (1, 9, 1), (2, 15, 3), (2, 16, 2), (3, 17, 2), (2, 31, 2), (2, 33, 3), (1, 1023, 2),
                        (2, 1024, 1), (2, 1025, 2), (1, 2047, 1), (2, 2048, 2), (1, 2049, 2), (1, 3073, 1), (4, 5, 6),
                        (5, 4, 3), (3, 1, 4)]:
            a = random_matrix(rng, m, k)
            b = random_matrix(rng, k, n)
            c = ta.matmul(matrix(a), matrix(b))
            self.assertEqual(c.shape, (m, n))
            for i in range(m):
                for j in range(n):
                    products = [a[i][t] * b[t][j] for t in range(k)]
                    want = order_sum(products)
                    dot = ta.dot(ta.array(a[i], ta.f64), ta.array([b[t][j] for t in range(k)], ta.f64))
                    self.assertEqual(bits(c[i, j]), bits(want), (m, k, n, i, j))
                    self.assertEqual(bits(dot), bits(want), (m, k, n, i, j))

    def test_specials_planted_at_lane_and_block_boundaries(self):
        rng = random.Random(77)
        for k in (1, 2, 15, 16, 17, 33, 1023, 1024, 1025, 2049):
            positions = sorted({0, k // 2, k - 1, 15, 16, 17, 1023, 1024, 1025} & set(range(k)))
            for pos in positions:
                for special in SPECIALS:
                    a = random_matrix(rng, 2, k)
                    b = random_matrix(rng, k, 2)
                    a[1][pos] = special
                    b[pos][0] = rng.choice(SPECIALS)
                    c = ta.matmul(matrix(a), matrix(b))
                    for i in range(2):
                        for j in range(2):
                            want = order_sum([a[i][t] * b[t][j] for t in range(k)])
                            self.assertEqual(bits(c[i, j]), bits(want), (k, pos, special, i, j))

    def test_nan_results_are_canonical(self):
        c = ta.matmul(matrix([[math.inf, 1.0]]), matrix([[0.0], [1.0]]))
        self.assertEqual(c.tobytes(), bits(math.nan))
        self.assertEqual(bits(math.nan), bytes.fromhex("000000000000f87f"))


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
                (tmp / "low").mkdir()
                (tmp / "low" / "prog.py").write_text(text, encoding="utf-8")
                ref = run_py(tmp / "ref", "prog.py")
                low = run_py(tmp / "low", "prog.py")
                self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
                self.assertEqual(low.stdout, ref.stdout)
                self.assertEqual(low.returncode, ref.returncode)

    def test_a_program_without_two_d_arrays_keeps_its_one_d_text(self):
        src = "import ail_array as ta\n\ndef main():\n    a = ta.zeros(4, ta.f64)\n    print(a + a, ta.sum(a))\n\nmain()\n"
        text, notes = lowered(src)
        self.assertEqual(notes, [])
        self.assertNotIn("_ail_tam", text)
        self.assertNotIn("_AilTAM", text)


REFUSED = [
    ("2-D int32", "import ail_array as ta\na = ta.zeros((2, 3), ta.int32)\n", "f64 in this stage"),
    ("2-D int32 literal", "import ail_array as ta\na = ta.array([[1, 2], [3, 4]], ta.int32)\n", "f64 in this stage"),
    ("3-D", "import ail_array as ta\na = ta.zeros((2, 3, 4), ta.f64)\n", "ta.zeros((rows, cols)"),
    ("matmul of 1-D", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = ta.matmul(a, a)\n", "2-D f64"),
    ("matmul int32", "import ail_array as ta\na = ta.zeros(3, ta.int32)\nb = ta.matmul(a, a)\n", "2-D f64"),
    ("sum of 2-D", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = ta.sum(a)\n", "ta.sum(M[i])"),
    ("dot of 2-D", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = ta.dot(a, a)\n", "on one row"),
    ("iterate", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nfor r in a:\n    pass\n", "range(len(M))"),
    ("list of 2-D", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = list(a)\n", "M[i].tolist()"),
    ("tolist", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = a.tolist()\n", "one row"),
    ("astype", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = a.astype(ta.f64)\n", "on one row"),
    ("slice index", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = a[0, 1:2]\n", "M[i, j]"),
    ("slice assignment", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\na[0:1] = a\n", "one row at a time"),
    ("row assignment of a number", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\na[0] = 1.0\n", "1-D f64 array"),
    ("2-D plus 1-D", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = ta.zeros(3, ta.f64)\nc = a + b\n", "row broadcast"),
    ("2-D plus int32", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = ta.zeros(3, ta.int32)\nc = a + b\n", "row broadcast"),
    ("floordiv", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = a // 2\n", "write instead"),
    ("truth", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nif a:\n    pass\n", "len(a) > 0"),
    ("shape unpure", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nr, c = ta.sqrt(a).shape\n", "bind the operand"),
    ("attribute", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = a.dtype\n", "M.T, M.shape"),
    ("bool dim", "import ail_array as ta\na = ta.zeros((True, 3), ta.f64)\n", "int length"),
    ("empty row", "import ail_array as ta\na = ta.array([[], []], ta.f64)\n", "ta.zeros((rows, 0)"),
    ("minimum 2-D with 1-D", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = ta.maximum(a, ta.zeros(3, ta.f64))\n",
     "loop over the rows"),
    ("wrapping on 2-D", "import ail_array as ta\na = ta.zeros((2, 3), ta.f64)\nb = ta.wrapping_add(a, a)\n", "one row"),
    ("bare Matrix annotation", "import ail_array as ta\ndef f(a: ta.Matrix):\n    return 1\n", "ta.Matrix[ta.f64]"),
    ("Matrix int32 annotation", "import ail_array as ta\ndef f(a: ta.Matrix[ta.int32]):\n    return 1\n", "ta.Matrix[ta.f64]"),
    ("param kinds", "import ail_array as ta\ndef f(a):\n    return a\nf(ta.zeros(1, ta.f64))\nf(ta.zeros((1, 1), ta.f64))\n",
     "annotate"),
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


@unittest.skipUnless(CC, "installed C compiler required")
class Native(unittest.TestCase):
    """Built programs print what CPython prints with the reference beside the program."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-array-t6-")
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

        jobs = [(n, m) for n in NAMES for m in ("default", "forced")] + [(n, "typed") for n in NAMES]
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
        _add(_n, _m)


if __name__ == "__main__":
    unittest.main()
