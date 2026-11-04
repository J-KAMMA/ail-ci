"""P1: the ten plain-Python programs in lab/pyperf/bench build and match CPython.

The programs are ordinary Python 3.12 written for this lab, each the algorithm
of a pyperformance benchmark.  Every program whose row in
lab/pyperf/RESULTS.md says it matches is compiled with the default command and
run beside `python3` at the small size; stdout and the exit status must agree.
The build and the run are the same commands lab/pyperf/run.py uses.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
PROGRAMS = ROOT.parent / "lab" / "pyperf" / "bench"
RESULTS = ROOT.parent / "lab" / "pyperf" / "RESULTS.md"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")


def load_runner():
    path = ROOT.parent / "lab" / "pyperf" / "run.py"
    spec = importlib.util.spec_from_file_location("ail_pyperf_run", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def matching_programs():
    """Rows of RESULTS.md whose `matches` cell is `yes`, in table order."""
    names = []
    for line in RESULTS.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[1] in ("typed", "general") and cells[2] == "yes":
            names.append(cells[0])
    return names


@unittest.skipUnless(CC, "installed C compiler required")
class PyperfLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-pyperf-test-")
        cls.dir = Path(cls.temp.name)
        cls.small = load_runner().SMALL

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in sorted(PROGRAMS.glob("*.py"))],
                         ["fannkuch.py", "float_bench.py", "generators.py", "nbody.py",
                          "nqueens.py", "raytrace.py", "richards.py", "scimark_fft.py",
                          "scimark_sor.py", "spectral_norm.py"])

    def test_results_has_programs(self):
        names = matching_programs()
        self.assertGreaterEqual(len(names), 8, "RESULTS.md lists %r" % names)
        for name in names:
            self.assertTrue((PROGRAMS / (name + ".py")).is_file(), name)
            self.assertIn(name, self.small, name)

    def test_matching_programs_match_cpython(self):
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        for name in matching_programs():
            with self.subTest(program=name):
                source = PROGRAMS / (name + ".py")
                work = self.dir / name
                work.mkdir(exist_ok=True)
                program = work / source.name
                shutil.copyfile(source, program)
                exe = work / (name + ".out")
                built = subprocess.run([sys.executable, "-B", CLI, "compile", program.name,
                                        "-o", exe.name],
                                       cwd=str(work), capture_output=True, text=True,
                                       timeout=300, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                expected = subprocess.run([sys.executable, "-B", source.name,
                                           str(self.small[name])],
                                          cwd=str(source.parent), capture_output=True,
                                          text=True, timeout=120, env=env)
                ran = subprocess.run([str(exe), str(self.small[name])], cwd=str(work),
                                     capture_output=True, text=True, timeout=300)
                self.assertEqual(ran.returncode, expected.returncode,
                                 "%s exit\nexpected stderr: %s\nactual stderr: %s"
                                 % (name, expected.stderr, ran.stderr))
                self.assertEqual(ran.stdout, expected.stdout, name)


if __name__ == "__main__":
    unittest.main()
