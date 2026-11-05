"""examples/mdtable: mdtable.py built by AIL, checked against CPython.

The formatter is compiled in the default mode and with AIL_UNIFIED_FORCE=1 and run on every
input in examples/mdtable/data with the option sets a user would pass (default, --check,
--sum 2). stdout, stderr and the exit status must agree with `python3` on the same source.
The one exception is the int64 overflow case: a --sum beyond int64 passes only if AIL prints
the exact value or stops loudly with an OverflowError line and no partial stdout.
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
MDTABLE = ROOT.parent / "examples" / "mdtable"
DATA = MDTABLE / "data"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

INPUTS = (
    "plain.md", "align.md", "escaped.md", "noouter.md", "ragged.md",
    "twotables.md", "fenced.md", "pipeprose.md", "empty.md", "formatted.md",
    "unicode.md", "bigsum.md",
)

OPTIONS = ([], ["--check"], ["--sum", "2"])

OVERFLOW_CASE = ("bigsum.md", ("--sum", "2"))


def run_cpython(args, inp):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    with inp.open("rb") as f:
        return subprocess.run([sys.executable, "-B", str(MDTABLE / "mdtable.py")] + args,
                              stdin=f, cwd=str(MDTABLE), capture_output=True, timeout=120,
                              env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class MdtableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-mdtable-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def build(self, mode):
        exe = self.dir / ("mdtable_%s" % mode)
        if exe.exists():
            return exe
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if mode == "unified":
            env["AIL_UNIFIED_FORCE"] = "1"
        else:
            env.pop("AIL_UNIFIED_FORCE", None)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", "mdtable.py",
                                "-o", str(exe)],
                               cwd=str(MDTABLE), capture_output=True, text=True,
                               timeout=600, env=env)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return exe

    def test_matches_cpython(self):
        for mode in ("default", "unified"):
            exe = self.build(mode)
            for name in INPUTS:
                inp = DATA / name
                for args in OPTIONS:
                    label = " ".join(args) if args else "default"
                    with self.subTest(mode=mode, input=name, args=label):
                        expected = run_cpython(args, inp)
                        with inp.open("rb") as f:
                            ran = subprocess.run([str(exe)] + args, stdin=f, cwd=str(MDTABLE),
                                                 capture_output=True, timeout=120)
                        if tuple(args) == OVERFLOW_CASE[1] and name == OVERFLOW_CASE[0]:
                            exact = (ran.returncode == expected.returncode
                                     and ran.stdout == expected.stdout
                                     and ran.stderr == expected.stderr)
                            loud = (ran.returncode != 0 and ran.stdout == b""
                                    and b"OverflowError" in ran.stderr)
                            self.assertTrue(exact or loud,
                                            "%s: neither exact nor a loud overflow stop\n"
                                            "exit %d, stdout %r, stderr %r"
                                            % (name, ran.returncode, ran.stdout, ran.stderr))
                            continue
                        self.assertEqual(ran.returncode, expected.returncode,
                                         "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                         % (name, label, expected.stderr, ran.stderr))
                        self.assertEqual(ran.stdout, expected.stdout, "%s %s stdout"
                                         % (name, label))
                        self.assertEqual(ran.stderr, expected.stderr, "%s %s stderr"
                                         % (name, label))


if __name__ == "__main__":
    unittest.main()
