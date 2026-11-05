"""examples/textcli: csvcut, uniqc and tsort built by AIL, checked against CPython.

Each tool is compiled in the default mode and with AIL_UNIFIED_FORCE=1 and run on every small
input in examples/textcli/data, with the options a user would pass. stdout, stderr and the exit
status must agree with `python3` on the same source.
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
TEXTCLI = ROOT.parent / "examples" / "textcli"
DATA = TEXTCLI / "data"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

TOOLS = ("csvcut", "uniqc", "tsort")

CASES = {
    "csvcut": [("csvcut_normal.csv", ["name", "city"]),
               ("csvcut_empty.csv", ["name"]),
               ("csvcut_quoted.csv", ["note", "id"])],
    "uniqc": [("uniqc_normal.txt", []),
              ("uniqc_empty.txt", ["-d"]),
              ("uniqc_odd.txt", ["-d"])],
    "tsort": [("tsort_normal.txt", []),
              ("tsort_empty.txt", []),
              ("tsort_cycle.txt", [])],
}


def run_cpython(tool, args, inp):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    with inp.open("rb") as f:
        return subprocess.run([sys.executable, "-B", str(TEXTCLI / (tool + ".py"))] + args,
                              stdin=f, cwd=str(TEXTCLI), capture_output=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class TextCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-textcli-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def build(self, tool, mode):
        exe = self.dir / ("%s_%s" % (tool, mode))
        if exe.exists():
            return exe
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if mode == "unified":
            env["AIL_UNIFIED_FORCE"] = "1"
        else:
            env.pop("AIL_UNIFIED_FORCE", None)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", tool + ".py",
                                "-o", str(exe)],
                               cwd=str(TEXTCLI), capture_output=True, text=True,
                               timeout=600, env=env)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return exe

    def test_matches_cpython(self):
        for mode in ("default", "unified"):
            for tool in TOOLS:
                exe = self.build(tool, mode)
                for name, args in CASES[tool]:
                    inp = DATA / name
                    with self.subTest(mode=mode, tool=tool, input=name, args=args):
                        expected = run_cpython(tool, args, inp)
                        with inp.open("rb") as f:
                            ran = subprocess.run([str(exe)] + args, stdin=f, cwd=str(TEXTCLI),
                                                 capture_output=True, timeout=120)
                        self.assertEqual(ran.returncode, expected.returncode,
                                         "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                         % (tool, name, expected.stderr, ran.stderr))
                        self.assertEqual(ran.stdout, expected.stdout, "%s %s stdout" % (tool, name))
                        self.assertEqual(ran.stderr, expected.stderr, "%s %s stderr" % (tool, name))


if __name__ == "__main__":
    unittest.main()
