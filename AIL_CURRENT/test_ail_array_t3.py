"""Stage T3a of docs/design/TYPED_ARRAY.md: `import ail_array` for f32 (1-D), lowered by python/pkg-v12/ailarray.py.

Before this stage every program that named `ta.f32` was refused by name ("f32 arrays are stage T3 ..."): 0 of the 8 case
files of array_t3_cases/ built. Now they all build and print what CPython prints with the reference `ail_array.py`:

* white box (CPython only): the lowered program text, run by CPython with no `ail_array.py` beside it, prints what the
  reference prints for the original program (stdout and exit code);
* native: the same programs built by the compiler in the default build and with AIL_UNIFIED_FORCE=1 print the same bytes
  as CPython with the reference (stdout and exit code), and the build is the typed path (no `note:` line);
* the store rule (0.1 into f32 is 0.10000000149011612), every element-wise op rounded once in binary64, the edge set of
  section 3.1 (both zeros, the smallest subnormal and normal, 2**24 + 1, halfway values, inf, NaN, overflow to inf),
  `ta.sum`/`ta.dot` at the lane and block boundaries of 3.5 (n = 0, 1, 15, 16, 17, 1023, 1024, 1025, 5000), `tolist`,
  `tobytes`, `repr`, and `astype` between f64 and f32 (the case files);
* f16 and int8 are still refused by name; f32 is 1-D only in this stage.
"""
import os
import shutil
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

CASES = ROOT / "array_t3_cases"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
NAMES = sorted(p.stem for p in CASES.glob("*.py"))


def run_py(directory, name):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", name], cwd=directory, capture_output=True, text=True, timeout=600, env=env)


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

    def test_f32_is_lowered(self):
        text, notes = lowered("import ail_array as ta\na = ta.zeros(3, ta.f32)\nprint(a)\n")
        self.assertEqual(notes, [])
        self.assertIn("_ail_ta3_zeros", text)

    def test_dtype_mix_raises_the_reference_text(self):
        src = ("import ail_array as ta\n\ndef main():\n"
               "    a = ta.zeros(2, ta.f32)\n    b = ta.zeros(2, ta.f64)\n    c = ta.zeros(2, ta.int32)\n"
               "    try:\n        print(a + b)\n    except TypeError as exc:\n        print('TypeError', exc)\n"
               "    try:\n        print(ta.minimum(a, b))\n    except TypeError as exc:\n        print('TypeError', exc)\n"
               "    try:\n        print(ta.dot(a, b))\n    except TypeError as exc:\n        print('TypeError', exc)\n"
               "    try:\n        print(a * c)\n    except TypeError as exc:\n        print('TypeError', exc)\n"
               "    try:\n        print(ta.sum(a, acc=ta.f64))\n    except ValueError as exc:\n        print('ValueError', exc)\n"
               "    print(a == b, a == c)\n\nmain()\n")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "ref").mkdir()
            shutil.copy(ROOT / "ail_array.py", tmp / "ref" / "ail_array.py")
            (tmp / "ref" / "prog.py").write_text(src, encoding="utf-8")
            text, notes = lowered(src)
            self.assertEqual(notes, [])
            (tmp / "low").mkdir()
            (tmp / "low" / "prog.py").write_text(text, encoding="utf-8")
            ref = run_py(tmp / "ref", "prog.py")
            low = run_py(tmp / "low", "prog.py")
        self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
        self.assertEqual(low.stdout, ref.stdout)
        self.assertEqual(low.returncode, ref.returncode)

    def test_f32_store_rule_in_the_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "ail_array.py").write_text((ROOT / "ail_array.py").read_text(encoding="utf-8"), encoding="utf-8")
            Path(tmp, "p.py").write_text("import ail_array as ta\nprint(ta.array([0.1], ta.f32)[0])\n", encoding="utf-8")
            done = run_py(tmp, "p.py")
        self.assertEqual(done.returncode, 0, done.stderr[-500:])
        self.assertEqual(done.stdout, "0.10000000149011612\n")


REFUSED = [
    ("f16", "import ail_array as ta\na = ta.array([1.0], ta.f16)\n", "stage T3"),
    ("int8", "import ail_array as ta\na = ta.zeros(3, ta.int8)\n", "stage T3"),
    ("f32 2-D zeros", "import ail_array as ta\na = ta.zeros((2, 3), ta.f32)\n", "f64"),
    ("f32 2-D literal", "import ail_array as ta\na = ta.array([[1.0, 2.0]], ta.f32)\n", "f64"),
    ("f32 floordiv", "import ail_array as ta\na = ta.zeros(3, ta.f32)\nb = a // 2\n", "write instead"),
    ("f32 mod", "import ail_array as ta\na = ta.zeros(3, ta.f32)\nb = a % 2\n", "write instead"),
    ("f32 unknown dtype", "import ail_array as ta\ndt = ta.f32\na = ta.zeros(3, dt)\n", "write instead"),
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
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-array-t3-")
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
            done = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", "prog.py", "-o", "prog.out"],
                                  cwd=d, capture_output=True, text=True, timeout=900, env=env)
            run = None
            if done.returncode == 0:
                run = subprocess.run([str(d / "prog.out")], capture_output=True, text=True, timeout=300)
            return job, done, run

        jobs = [(n, m) for n in NAMES for m in ("default", "forced")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            cls.out = dict(pool.map(lambda j: (j, build(j)), jobs))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, name, mode):
        job, done, run = self.out[(name, mode)][0], self.out[(name, mode)][1], self.out[(name, mode)][2]
        self.assertEqual(done.returncode, 0, (done.stdout + done.stderr)[-1500:])
        self.assertNotIn("built on the general path", done.stderr)
        ref = self.ref[name]
        self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
        self.assertEqual(run.stdout, ref.stdout)
        self.assertEqual(run.returncode, ref.returncode)


def _add(name, mode):
    setattr(Native, "test_%s_%s" % (name, mode), lambda self: self.check(name, mode))


for _n in NAMES:
    for _m in ("default", "forced"):
        _add(_n, _m)


if __name__ == "__main__":
    unittest.main()
