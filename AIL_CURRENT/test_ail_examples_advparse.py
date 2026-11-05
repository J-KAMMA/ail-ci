"""examples/advparse: advparse built by AIL, checked against CPython.

The program is compiled once in the default mode and once with
AIL_UNIFIED_FORCE=1, then run on every script in examples/advparse/scripts.
Standard output and the exit status must agree with `python3` on the same
source. The module skips when no C compiler is installed.
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
APP = ROOT.parent / "examples" / "advparse"
PROGRAM = APP / "advparse.py"
SCRIPTS = sorted((APP / "scripts").glob("*.txt"))
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")


def python_run(script):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    with script.open("rb") as f:
        return subprocess.run([sys.executable, "-B", str(PROGRAM)], stdin=f,
                              capture_output=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class AdvparseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-advparse-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def build(self, mode):
        exe = self.dir / ("advparse_%s" % mode)
        if exe.exists():
            return exe
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if mode == "unified":
            env["AIL_UNIFIED_FORCE"] = "1"
        else:
            env.pop("AIL_UNIFIED_FORCE", None)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(PROGRAM),
                                "-o", str(exe)],
                               cwd=str(APP), capture_output=True, text=True,
                               timeout=600, env=env)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return exe

    def test_matches_cpython(self):
        for mode in ("default", "unified"):
            exe = self.build(mode)
            for script in SCRIPTS:
                with self.subTest(mode=mode, script=script.name):
                    expected = python_run(script)
                    with script.open("rb") as f:
                        ran = subprocess.run([str(exe)], stdin=f, cwd=str(APP),
                                             capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (script.name, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, "%s stdout" % script.name)
                    self.assertEqual(ran.stderr, expected.stderr, "%s stderr" % script.name)


if __name__ == "__main__":
    unittest.main()
