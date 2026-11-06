"""The ail_array core-subset conformance table (job fdarr2; docs/design/TYPED_ARRAY.md, "Core subset").

Cells: dtype (f64, f32, int32) x op (+ - * / // %, unary -, abs, minimum, maximum, sum, dot, min, max, argmin, argmax, matmul),
51 in all. Every line a case in array_core_cases/ prints starts with its cell ("add f32|"). A built cell matches when, in the
default build and with AIL_UNIFIED_FORCE=1, the lines of that cell are exactly the lines CPython prints with the reference
`ail_array.py` beside the program (and the exit status is the same). A refused cell is refused at compile time by name
(file:line and `write instead:`), never built with other output. The test fails on any cell that is neither: 0 wrong.

Before this job f32 and int32 `matmul` were refused (2-D arrays were f64 only, and the reference itself refused them);
the reference now defines them (design 3.7) and both are built.
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
sys.path.insert(0, str(PKG))
import ailarray  # noqa: E402

CASES = ROOT / "array_core_cases"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
NAMES = sorted(p.stem for p in CASES.glob("*.py"))
DTYPES = ("f64", "f32", "int32")
OPS = ("add", "sub", "mul", "div", "floordiv", "mod", "neg", "abs", "minimum", "maximum", "sum", "dot", "min", "max",
       "argmin", "argmax", "matmul")
SYM = {"div": "/", "floordiv": "//", "mod": "%"}
# cells refused by name: float // and %, int32 / (the reference raises TypeError at run time; the compiler refuses them)
REFUSED = {("floordiv", "f64"), ("mod", "f64"), ("floordiv", "f32"), ("mod", "f32"), ("div", "int32")}


def refused_source(op, dt):
    return "import ail_array as ta\na = ta.zeros(3, ta.%s)\nb = a %s a\n" % (dt, SYM[op])


def run_py(directory, name):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", name], cwd=directory, capture_output=True, text=True, timeout=600, env=env)


def cells_of(text):
    out = {}
    for line in text.splitlines():
        head, sep, _ = line.partition("|")
        if sep:
            out.setdefault(head, []).append(line)
    return out


class Table(unittest.TestCase):
    def test_every_cell_is_covered_or_refused(self):
        seen = set()
        for name in NAMES:
            with tempfile.TemporaryDirectory() as tmp:
                shutil.copy(ROOT / "ail_array.py", tmp)
                shutil.copy(CASES / (name + ".py"), Path(tmp, "prog.py"))
                ref = run_py(tmp, "prog.py")
                self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
                seen.update(cells_of(ref.stdout))
        for dt in DTYPES:
            for op in OPS:
                cell = "%s %s" % (op, dt)
                if (op, dt) in REFUSED:
                    self.assertNotIn(cell, seen)
                else:
                    self.assertIn(cell, seen)

    def test_refused_cells_name_the_operator(self):
        for op, dt in sorted(REFUSED):
            with self.subTest(cell=(op, dt)):
                src = refused_source(op, dt)
                notes = []
                self.assertEqual(ailarray.rewrite_text(src, notes), src)
                self.assertTrue(notes)
                self.assertIn("%s on %s arrays" % (SYM[op], dt), notes[0][1])
                self.assertIn("write instead", notes[0][1])


class WhiteBox(unittest.TestCase):
    def test_lowered_text_equals_reference(self):
        for name in NAMES:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                source = (CASES / (name + ".py")).read_text(encoding="utf-8")
                (tmp / "ref").mkdir()
                (tmp / "low").mkdir()
                shutil.copy(ROOT / "ail_array.py", tmp / "ref")
                (tmp / "ref" / "prog.py").write_text(source, encoding="utf-8")
                notes = []
                (tmp / "low" / "prog.py").write_text(ailarray.rewrite_text(source, notes), encoding="utf-8")
                self.assertEqual(notes, [])
                ref = run_py(tmp / "ref", "prog.py")
                low = run_py(tmp / "low", "prog.py")
                self.assertEqual(low.stdout, ref.stdout)
                self.assertEqual(low.returncode, ref.returncode)


@unittest.skipUnless(CC, "installed C compiler required")
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-array-core-")
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
                                  cwd=d, capture_output=True, text=True, timeout=1800, env=env)
            run = None
            if done.returncode == 0:
                run = subprocess.run([str(d / "prog.out")], capture_output=True, text=True, timeout=600)
            return job, done, run

        jobs = [(n, m) for n in NAMES for m in ("default", "forced")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            cls.out = dict(pool.map(lambda j: (j, build(j)), jobs))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_cells(self):
        wrong = []
        matched = set()
        for (name, mode), (job, done, run) in sorted(self.out.items()):
            ref = self.ref[name]
            if done.returncode != 0:
                wrong.append((name, mode, "build failed", (done.stdout + done.stderr)[-800:]))
                continue
            if run.returncode != ref.returncode:
                wrong.append((name, mode, "exit status %d, reference %d" % (run.returncode, ref.returncode), run.stderr[-400:]))
            want, got = cells_of(ref.stdout), cells_of(run.stdout)
            for cell in sorted(set(want) | set(got)):
                if want.get(cell) == got.get(cell):
                    matched.add((cell, mode))
                else:
                    wrong.append((name, mode, cell, ""))
            if run.stdout != ref.stdout:
                wrong.append((name, mode, "stdout differs outside the cell lines", ""))
        self.assertEqual(wrong, [])
        built = [(op, dt) for dt in DTYPES for op in OPS if (op, dt) not in REFUSED]
        for op, dt in built:
            for mode in ("default", "forced"):
                self.assertIn(("%s %s" % (op, dt), mode), matched)
        print("\nail_array core table: %d cells, %d match in both builds, %d refused by name, 0 wrong"
              % (len(DTYPES) * len(OPS), len(built), len(REFUSED)), file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
