"""Every fenced ```python block in README.md is a complete program that runs like CPython.

The blocks are extracted from the top-level README, run through the installed-style `ail run`
command in packaging/ail_lang, and compared with CPython 3.12 (return code and stdout).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
README = REPO / "README.md"
PACKAGING = REPO / "packaging"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
FENCE = re.compile(r"^```python[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)


def python_blocks():
    text = README.read_text(encoding="utf-8")
    return [(text.count("\n", 0, match.start()) + 1, match.group(1)) for match in FENCE.finditer(text)]


@unittest.skipUnless(CC, "needs a C compiler")
@unittest.skipUnless((PACKAGING / "ail_lang" / "cli.py").is_file(), "packaging/ is absent")
class ReadmeExamples(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-readme-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def ail(self, *args):
        env = dict(os.environ, PYTHONPATH=str(PACKAGING), AIL_SDK_DIR=str(ROOT), PYTHONUTF8="1",
                   AIL_CACHE=str(self.dir / "cache"))
        env.pop("AIL_NO_CACHE", None)
        return subprocess.run([sys.executable, "-B", "-m", "ail_lang", *args], cwd=self.dir, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=600)

    def test_readme_has_a_python_example(self):
        self.assertTrue(python_blocks(), "README.md has no fenced ```python block")

    def test_examples_run_through_ail_like_cpython(self):
        for number, (line, body) in enumerate(python_blocks(), 1):
            with self.subTest(readme_line=line):
                source = self.dir / ("example-%d.py" % number)
                source.write_text(body, encoding="utf-8")
                want = subprocess.run([sys.executable, str(source)], cwd=self.dir, capture_output=True,
                                      text=True, encoding="utf-8", timeout=60,
                                      env=dict(os.environ, PYTHONUTF8="1"))
                self.assertEqual(want.returncode, 0, "CPython failed:\n%s" % want.stderr[-1500:])
                got = self.ail("run", source.name)
                self.assertEqual(got.returncode, want.returncode,
                                 "ail run exit %d, stderr:\n%s" % (got.returncode, got.stderr[-1500:]))
                self.assertEqual(got.stdout, want.stdout,
                                 "README.md:%d stdout differs from CPython\nCPython:\n%s\nAIL:\n%s"
                                 % (line, want.stdout[-1500:], got.stdout[-1500:]))


if __name__ == "__main__":
    unittest.main()
