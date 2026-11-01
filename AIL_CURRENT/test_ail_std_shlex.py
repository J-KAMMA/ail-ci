"""G5a: `import shlex` in compiled programs (bundled stdlib/shlex.py) against CPython's shlex.

The twelve programs in lab/stdlib/shlex/ use split, quote, join and the shlex lexer class the way
ordinary code does: comments, posix and non-posix quoting, punctuation_chars, custom delimiters,
wordchars, pushback, push_source, iteration and the ValueError cases.  Each is compiled with the
default command and run beside `python3` on the same source; stdout and the exit status must agree.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "shlex"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibShlexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-shlex-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources],
                         ["01_command_line.py", "02_config_comments.py", "03_non_posix.py",
                          "04_lexer_iteration.py", "05_get_token.py", "06_punctuation.py",
                          "07_wordchars.py", "08_custom_delimiters.py", "09_errors.py",
                          "10_build_command.py", "11_sources.py", "12_shell_tokens.py"])

    def test_programs_match_cpython(self):
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        for source in self.sources:
            with self.subTest(program=source.name):
                work = self.dir / source.stem
                work.mkdir(exist_ok=True)
                program = work / source.name
                shutil.copyfile(source, program)
                exe = work / (source.stem + ".out")
                built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                        "--syntax", "python", "-o", str(exe)],
                                       cwd=str(work), capture_output=True, text=True,
                                       timeout=600, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                expected = run_cpython(program)
                ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                     text=True, timeout=120)
                self.assertEqual(ran.returncode, expected.returncode,
                                 "%s exit\nexpected stderr: %s\nactual stderr: %s"
                                 % (source.name, expected.stderr, ran.stderr))
                self.assertEqual(ran.stdout, expected.stdout, source.name)


if __name__ == "__main__":
    unittest.main()
