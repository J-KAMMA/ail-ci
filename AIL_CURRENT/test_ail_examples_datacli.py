"""examples/datacli: the two data tools compiled by AIL against CPython.

`examples/datacli/histo.py` and `ini2json.py` are ordinary annotated Python.
Each is compiled in the default build and with AIL_UNIFIED_FORCE=1, then run
on its normal and edge inputs beside `python3`; stdout, stderr and the exit
status must agree.
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
BASE = ROOT.parent / "examples" / "datacli"
DATA = BASE / "data"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

TOOLS = {
    "histo": ["5"],
    "ini2json": [],
}
INPUTS = {
    "histo": ["histo_normal.txt", "histo_empty.txt", "histo_equal.txt", "histo_bigint.txt"],
    "ini2json": ["ini_normal.ini", "ini_empty.ini", "ini_bad.ini", "ini_unicode.ini"],
}


def run_cpython(tool, args, data):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(BASE / (tool + ".py"))] + args,
                          input=data, cwd=str(BASE), capture_output=True,
                          timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class DatacliExamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-datacli-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_inputs_exist(self):
        for tool, names in INPUTS.items():
            for name in names:
                self.assertTrue((DATA / name).is_file(), name)
            self.assertTrue((BASE / (tool + ".py")).is_file(), tool)

    def test_tools_match_cpython(self):
        for tool in ("histo", "ini2json"):
            source = BASE / (tool + ".py")
            self.assertTrue(source.is_file(), tool)
            for forced in (False, True):
                work = self.dir / (tool + ("_forced" if forced else "_default"))
                work.mkdir(exist_ok=True)
                exe = work / (tool + ".out")
                env = dict(os.environ, AIL_NO_CACHE="1")
                env.pop("PYTHONPATH", None)
                if forced:
                    env["AIL_UNIFIED_FORCE"] = "1"
                built = subprocess.run([sys.executable, "-B", CLI, "compile", str(source),
                                        "-o", str(exe)],
                                       cwd=str(work), capture_output=True, text=True,
                                       timeout=600, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                for name in INPUTS[tool]:
                    with self.subTest(tool=tool, input=name, forced=forced):
                        data = (DATA / name).read_bytes()
                        expected = run_cpython(tool, TOOLS[tool], data)
                        ran = subprocess.run([str(exe)] + TOOLS[tool], input=data,
                                             cwd=str(work), capture_output=True,
                                             timeout=120)
                        self.assertEqual(ran.returncode, expected.returncode,
                                         "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                         % (tool, name, expected.stderr, ran.stderr))
                        self.assertEqual(ran.stdout, expected.stdout, "%s %s stdout" % (tool, name))
                        self.assertEqual(ran.stderr, expected.stderr, "%s %s stderr" % (tool, name))


if __name__ == "__main__":
    unittest.main()
