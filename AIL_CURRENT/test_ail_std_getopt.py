"""getopt1: `import getopt` in compiled programs (bundled stdlib/getopt.py) against CPython's getopt.

The twelve programs in lab/stdlib/getopt/ use short options (flags, values, grouped and attached
values), long options and unique prefixes, `--`, stopping at the first non-option, `gnu_getopt`
with a leading `+`, the five error kinds through `GetoptError.msg`/`.opt`/`str`, the `getopt.error`
alias, usage on stderr with `sys.exit(2)`, and int conversion of option values.  Every passing
program is compiled with the default command and with AIL_UNIFIED_FORCE=1 and run beside `python3`
on the same source; stdout and the exit status must agree.

09_error_alias.py is refused because `except getopt.error` is a module attribute naming an
exception class (compiler follow-up, see lab/stdlib/getopt/RESULTS.md).  11_convert_int.py builds
but stops loudly at the third value, which is beyond int64; CPython prints it, so that program is
not compared.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "getopt"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_short_options.py",
    "02_long_options.py",
    "03_prefix_and_double_dash.py",
    "04_stop_at_nonoption.py",
    "05_gnu_mixed.py",
    "06_gnu_plus.py",
    "07_errors_short.py",
    "08_errors_long.py",
    "10_usage_exit.py",
    "12_values_and_repeats.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibGetoptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-getopt-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources],
                         ["01_short_options.py", "02_long_options.py", "03_prefix_and_double_dash.py",
                          "04_stop_at_nonoption.py", "05_gnu_mixed.py", "06_gnu_plus.py",
                          "07_errors_short.py", "08_errors_long.py", "09_error_alias.py",
                          "10_usage_exit.py", "11_convert_int.py", "12_values_and_repeats.py"])
        self.assertEqual(len(PASSING), 10)

    def test_programs_match_cpython(self):
        base = dict(os.environ, AIL_NO_CACHE="1")
        base.pop("PYTHONPATH", None)
        for source in self.sources:
            if source.name not in PASSING:
                continue
            for mode in ("default", "forced-general"):
                with self.subTest(program=source.name, build=mode):
                    work = self.dir / (source.stem + "-" + mode)
                    work.mkdir(exist_ok=True)
                    program = work / source.name
                    shutil.copyfile(source, program)
                    exe = work / (source.stem + ".out")
                    env = dict(base)
                    if mode == "forced-general":
                        env["AIL_UNIFIED_FORCE"] = "1"
                    else:
                        env.pop("AIL_UNIFIED_FORCE", None)
                    built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                            "--syntax", "python", "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    expected = run_cpython(program)
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (source.name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, source.name + " " + mode)


if __name__ == "__main__":
    unittest.main()
