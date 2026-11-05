"""examples/algos: twelve plain-Python algorithms against CPython at a small size.

Each passing program is built with the default command and run with `--small`; stdout and
the exit status must agree with `python3` on the same source.  `rpn.py` builds but stops
loudly on `2 ** 70`, which is beyond int64, so it is not compared (CPython prints the exact
value; the int64 stop is documented in examples/algos/RESULTS.md).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
PROGRAMS = ROOT.parent / "examples" / "algos"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

ALL = [
    "dijkstra.py",
    "huffman.py",
    "knapsack.py",
    "lcs.py",
    "levenshtein.py",
    "life.py",
    "mandelbrot.py",
    "rpn.py",
    "sieve.py",
    "sudoku.py",
    "topo.py",
    "wordfreq.py",
]
PASSING = [name for name in ALL if name != "rpn.py"]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path), "--small"],
                          cwd=str(path.parent), capture_output=True, text=True,
                          timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class ExamplesAlgosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-algos-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_programs_exist(self):
        self.assertEqual(sorted(path.name for path in PROGRAMS.glob("*.py")
                                if path.name != "run.py"), ALL)
        self.assertEqual(len(PASSING), 11)

    def test_programs_match_cpython(self):
        base = dict(os.environ, AIL_NO_CACHE="1")
        base.pop("PYTHONPATH", None)
        for name in PASSING:
            with self.subTest(program=name):
                work = self.dir / name[:-3]
                work.mkdir(exist_ok=True)
                source = PROGRAMS / name
                program = work / name
                shutil.copyfile(source, program)
                exe = work / (name[:-3] + ".out")
                built = subprocess.run(
                    [sys.executable, "-B", CLI, "compile", str(program),
                     "--syntax", "python", "-o", str(exe)],
                    cwd=str(work), capture_output=True, text=True, timeout=600, env=base)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                expected = run_cpython(source)
                ran = subprocess.run([str(exe), "--small"], cwd=str(work),
                                     capture_output=True, text=True, timeout=120)
                self.assertEqual(ran.returncode, expected.returncode,
                                 "%s exit\nexpected stderr: %s\nactual stderr: %s"
                                 % (name, expected.stderr, ran.stderr))
                self.assertEqual(ran.stdout, expected.stdout, name)


if __name__ == "__main__":
    unittest.main()
