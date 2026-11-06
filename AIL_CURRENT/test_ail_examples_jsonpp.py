"""examples/jsonpp: the JSON pretty-printer built by AIL, checked against CPython.

jsonpp.py is compiled in the default mode and with AIL_UNIFIED_FORCE=1 and run on every input in
examples/jsonpp/data, in four option sets. stdout, the last line of stderr and the exit status
must agree with `python3` on the same source.

surrogate.json is skipped: AIL's 16-bit str refuses chr() of a surrogate code unit at run time,
which is a loud stop recorded in examples/jsonpp/RESULTS.md, not a wrong answer.
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
JSONPP = ROOT.parent / "examples" / "jsonpp"
DATA = JSONPP / "data"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

OPTIONS = [
    [],
    ["--indent", "4", "--sort-keys"],
    ["--compact"],
    ["--check"],
]

SKIP = {"surrogate.json"}


def run_cpython(args, inp):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    with inp.open("rb") as f:
        return subprocess.run([sys.executable, "-B", str(JSONPP / "jsonpp.py")] + args,
                              stdin=f, cwd=str(JSONPP), capture_output=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class JsonppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-jsonpp-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def build(self, mode):
        exe = self.dir / ("jsonpp_" + mode)
        if exe.exists():
            return exe
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if mode == "unified":
            env["AIL_UNIFIED_FORCE"] = "1"
        else:
            env.pop("AIL_UNIFIED_FORCE", None)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", "jsonpp.py",
                                "-o", str(exe)],
                               cwd=str(JSONPP), capture_output=True, text=True,
                               timeout=600, env=env)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return exe

    def test_matches_cpython(self):
        names = sorted(p.name for p in DATA.glob("*.json") if p.name not in SKIP)
        self.assertEqual(len(names), 15)
        for mode in ("default", "unified"):
            exe = self.build(mode)
            for name in names:
                inp = DATA / name
                for args in OPTIONS:
                    with self.subTest(mode=mode, input=name, args=args):
                        expected = run_cpython(args, inp)
                        with inp.open("rb") as f:
                            ran = subprocess.run([str(exe)] + args, stdin=f, cwd=str(JSONPP),
                                                 capture_output=True, timeout=120)
                        self.assertEqual(ran.returncode, expected.returncode,
                                         "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                         % (name, args, expected.stderr, ran.stderr))
                        self.assertEqual(ran.stdout, expected.stdout, "%s %s stdout" % (name, args))
                        self.assertEqual(ran.stderr, expected.stderr, "%s %s stderr" % (name, args))


if __name__ == "__main__":
    unittest.main()
