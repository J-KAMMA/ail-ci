"""H1: an AIL build keeps the hardening properties it has today (PIE, NX, full RELRO, canary).

This measures, it does not change the build.  The four properties are what Ubuntu 24.04's gcc 13
defaults give a plain `cc -O2` link; if a build change ever loses one, this test fails instead of
the loss going unnoticed.  Only properties observed to be true today are asserted.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
CHECK = ROOT.parent / "tools" / "hardening_check.py"
SOURCE = ROOT.parent / "lab" / "hardening" / "rec_tree.py"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
READELF = shutil.which("readelf")
EXPECTED = "nodes=500 sum=11808 depth=6\n"


@unittest.skipUnless(CC, "installed C compiler required")
@unittest.skipUnless(READELF, "readelf required")
class HardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-hardening-test-")
        cls.dir = Path(cls.temp.name)
        cls.exe = cls.dir / "rec_tree"
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(SOURCE), "-o", str(cls.exe)],
                               cwd=str(cls.dir), capture_output=True, text=True, timeout=600, env=env)
        if built.returncode != 0:
            cls.temp.cleanup()
            raise AssertionError("the AIL build failed:\n" + built.stderr[-2000:])
        measured = subprocess.run([sys.executable, str(CHECK), str(cls.exe)],
                                  capture_output=True, text=True, timeout=120)
        if measured.returncode != 0:
            cls.temp.cleanup()
            raise AssertionError("hardening_check failed:\n" + measured.stderr[-2000:])
        cls.row = json.loads(measured.stdout.splitlines()[0])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_pie(self):
        self.assertTrue(self.row["pie"], self.row)

    def test_nx(self):
        self.assertTrue(self.row["nx"], self.row)

    def test_relro(self):
        self.assertEqual(self.row["relro"], "full", self.row)

    def test_canary(self):
        self.assertTrue(self.row["canary"], self.row)

    def test_program_still_runs(self):
        ran = subprocess.run([str(self.exe)], capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.returncode, 0, ran.stderr[-2000:])
        self.assertEqual(ran.stdout, EXPECTED)


if __name__ == "__main__":
    unittest.main()
