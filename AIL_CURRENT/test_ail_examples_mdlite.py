"""mdlite builds with the default AIL mode and matches CPython on ten inputs.

The example app examples/mdlite/mdlite.py is compiled once, then run beside
`python3` on the six hand-written inputs in examples/mdlite/data and on four
repository documents, plus a missing-file case. Standard output, standard
error and the exit status must agree byte for byte. The module skips when no C
compiler is installed.

One input, a code point above U+FFFF, is a known 16-bit-runtime refusal and is
recorded in examples/mdlite/RESULTS.md instead of being compared here.
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
APP = ROOT.parent / "examples" / "mdlite"
PROGRAM = APP / "mdlite.py"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

DATA_INPUTS = tuple(
    APP / "data" / name
    for name in ("headings.md", "inline.md", "lists.md", "quotes.md", "fences.md", "empty.md")
)
DOC_INPUTS = (
    ROOT.parent / "docs" / "tutorial.md",
    ROOT.parent / "docs" / "QUICKSTART.md",
    ROOT.parent / "docs" / "INSTALL.md",
    ROOT.parent / "README.md",
)


def python_run(arguments):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(PROGRAM), *arguments],
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class MdliteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-mdlite-")
        cls.dir = Path(cls.temp.name)
        cls.binary = cls.dir / "mdlite.bin"
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        built = subprocess.run(
            [sys.executable, "-B", CLI, "compile", str(PROGRAM), "-o", str(cls.binary)],
            capture_output=True, text=True, timeout=600, env=env)
        if built.returncode != 0:
            raise AssertionError("mdlite did not build: %s%s" % (built.stdout, built.stderr))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def check(self, arguments):
        expected = python_run(arguments)
        ran = subprocess.run([str(self.binary), *arguments],
                             capture_output=True, text=True, timeout=120)
        label = " ".join(arguments)
        self.assertEqual(ran.returncode, expected.returncode,
                         "mdlite %s exit status\nCPython stderr: %s\nAIL stderr: %s"
                         % (label, expected.stderr, ran.stderr))
        self.assertEqual(ran.stdout, expected.stdout, "mdlite %s stdout" % label)
        self.assertEqual(ran.stderr, expected.stderr, "mdlite %s stderr" % label)
        return expected, ran

    def test_hand_inputs(self):
        for path in DATA_INPUTS:
            with self.subTest(input=path.name):
                self.check([str(path)])

    def test_repository_documents(self):
        for path in DOC_INPUTS:
            with self.subTest(input=path.name):
                self.check([str(path)])

    def test_missing_file(self):
        missing = str(self.dir / "absent-input.md")
        expected, ran = self.check([missing])
        self.assertEqual(ran.returncode, 1)
        self.assertEqual(ran.stderr, "mdlite: cannot open " + missing + "\n")


if __name__ == "__main__":
    unittest.main()
