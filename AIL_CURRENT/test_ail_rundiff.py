"""`ail run --diff` (packaging/ail_lang/cli.py, docs/CLI.md): run the program natively and under
CPython with the same input, and stop loudly on any difference.

* agree on a small program that reads stdin and takes arguments, exiting with its own code;
* DIFFER on stdout, on the exit code and on the exception type (a different traceback text for the
  same type is still agreement);
* DIFFER on stdout against a fake interpreter (`--python` pointing at a tiny script that prints
  another line), which is also how the reserved exit code 3 is checked;
* loud stop by design on an int64 overflow (exit 4), and on a build-time refusal CPython accepts;
* `timeout: native` with `--timeout 1` (exit 124);
* the `--json` object's shape.

Every test drives the real `ail` entry point (`python -m ail_lang`) with `AIL_SDK_DIR` pointing at
this checkout, so it exercises the packaged command exactly as a user does. Building needs a C
compiler (skipped without one); the module is skipped when packaging/ is not beside this directory.
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
PACKAGING = ROOT.parent / "packaging"
CC = (os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
      or shutil.which("zig"))

AGREE = '''\
import sys

data = sys.stdin.read()
print("read", len(data))
for argument in sys.argv[1:]:
    print("arg", argument)
'''

EXIT_CODE = '''\
import sys

print("before")
sys.exit(3)
'''

RAISES = '''\
def main() -> None:
    xs: list[int] = [1]
    print(xs[9])


main()
'''

OVERFLOW = '''\
import sys


def main() -> None:
    n = int(sys.argv[1])
    print(n * 4)


main()
'''

SLOW = '''\
import time


def main() -> None:
    time.sleep(5)
    print("done")


main()
'''

# the body a stand-in interpreter runs: it ignores the source and prints one fixed line
FAKE_PYTHON = '''\
import sys
print("from the fake interpreter")
'''


def setUpModule():
    if not (PACKAGING / "ail_lang" / "cli.py").is_file():
        raise unittest.SkipTest("packaging/ail_lang is not beside AIL_CURRENT")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-rundiff-test-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def ail(self, *args, stdin=b"", timeout=600):
        environment = dict(os.environ, PYTHONPATH=str(PACKAGING), AIL_SDK_DIR=str(ROOT), PYTHONUTF8="1",
                           AIL_CACHE=str(self.dir / "cache"))
        environment.pop("AIL_NO_CACHE", None)
        return subprocess.run([sys.executable, "-B", "-m", "ail_lang", *map(str, args)], cwd=self.dir,
                              env=environment, input=stdin, capture_output=True, timeout=timeout)

    def fake_python(self, name="fake_python.py", body=None):
        """A tiny stand-in for the interpreter: an executable script with a shebang, so `--python`
        accepts it exactly as it accepts a real interpreter path."""
        path = self.dir / name
        text = "#!%s\n%s" % (sys.executable, FAKE_PYTHON if body is None else body)
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)
        return path


@unittest.skipUnless(CC, "no C compiler")
class DiffMode(Base):
    def test_agree_on_a_program_with_stdin_and_arguments(self):
        program = self.write("agree.py", AGREE)
        done = self.ail("run", "--diff", program, "one", "two", stdin=b"abcdef\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, b"read 7\narg one\narg two\n")
        self.assertIn(b"ail diff: agree", done.stderr)

    def test_differ_on_stdout_against_a_fake_interpreter(self):
        program = self.write("agree.py", AGREE)
        done = self.ail("run", "--diff", "--python", self.fake_python(), program, stdin=b"abcdef\n")
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertIn(b"ail diff: DIFFER: stdout line 1", done.stderr)
        self.assertIn(b"read 7", done.stderr)
        self.assertIn(b"from the fake interpreter", done.stderr)
        self.assertNotIn(b"ail diff: agree", done.stderr)

    def test_differ_on_the_exit_code(self):
        program = self.write("exit.py", "print('same')\n")
        done = self.ail("run", "--diff", "--python", self.fake_python(), program)
        self.assertEqual(done.returncode, 3, done.stderr)
        # both printed one line, so the difference is the exit code: the fake one exits 0, the
        # native program too -- use a program that exits nonzero to make the codes differ
        fake = self.fake_python("fake_fail.py", "import sys\nprint('same')\nsys.exit(2)\n")
        done = self.ail("run", "--diff", "--python", fake, program)
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertIn(b"ail diff: DIFFER: exit code 0 vs 2", done.stderr)

    def test_agree_when_the_exception_type_matches_though_the_text_differs(self):
        # CPython and AIL write different traceback text for the same IndexError; only the type counts
        program = self.write("raises.py", RAISES)
        done = self.ail("run", "--diff", program)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn(b"ail diff: agree", done.stderr)
        self.assertIn(b"IndexError", done.stderr)

    def test_differ_on_the_exception_type(self):
        program = self.write("raises.py", RAISES)
        fake = self.fake_python("fake_wrong_exception.py", "raise TypeError('not the same')\n")
        done = self.ail("run", "--diff", "--python", fake, program)
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertIn(b"ail diff: DIFFER: exception IndexError vs TypeError", done.stderr)

    def test_loud_stop_by_design_on_int64_overflow(self):
        program = self.write("overflow.py", OVERFLOW)
        done = self.ail("run", "--diff", program, "4611686018427387904")
        self.assertEqual(done.returncode, 4, done.stderr)
        self.assertIn(b"ail diff: loud stop by design:", done.stderr)
        self.assertIn(b"OverflowError: integer overflow in *", done.stderr)

    def test_loud_stop_by_design_when_the_build_refuses_a_program_cpython_runs(self):
        program = self.write("refused.py", '''\
def main() -> None:
    d = {}
    d["k"] = 1
    view = d.items()
    print(len(view))


main()
''')
        done = self.ail("run", "--diff", program)
        # either the compiler builds it (then the runs agree) or it refuses it by name; both are
        # acceptable, but a refusal must be reported as a by-design stop, never as a difference
        self.assertIn(done.returncode, (0, 4), done.stderr)
        if done.returncode == 4:
            self.assertIn(b"ail diff: loud stop by design:", done.stderr)

    def test_differ_not_loud_stop_when_an_unrecognised_build_stop_cpython_runs(self):
        # a broken link or a bad module path is a toolchain failure, not one of AIL's documented
        # limits: it must be a difference (exit 3), never "loud stop by design" (exit 4)
        program = self.write("agree.py", AGREE)
        for options in (["--link", str(self.dir / "libnope.so")],
                        ["-I", str(self.dir / "no-such-dir")]):
            with self.subTest(options=options):
                done = self.ail("run", "--diff", *options, program, stdin=b"ab\n")
                self.assertEqual(done.returncode, 3, done.stderr)
                self.assertIn(b"ail diff: DIFFER: no native program, the build stopped", done.stderr)
                self.assertNotIn(b"loud stop by design", done.stderr)

    def test_differ_when_the_build_stops_and_cpython_fails_too(self):
        program = self.write("fails_both_ways.py", """\
import sys


def main() -> None:
    d = {}
    d["k"] = 1
    view = d.items()
    print(len(view))
    sys.exit(2)


main()
""")
        done = self.ail("run", "--diff", program)
        # the compiler may accept this program; when it does not, the build stop must be named
        if done.returncode == 3:
            self.assertTrue(b"DIFFER: no native program, the build stopped" in done.stderr
                            or b"DIFFER: exit code" in done.stderr, done.stderr)

    def test_timeout_of_the_native_run(self):
        program = self.write("slow.py", SLOW)
        done = self.ail("run", "--diff", "--timeout", "1", program)
        self.assertEqual(done.returncode, 124, done.stderr)
        self.assertIn(b"ail diff: timeout: native", done.stderr)

    def test_json_shape_on_agreement(self):
        program = self.write("agree.py", AGREE)
        done = self.ail("run", "--diff", "--json", program, stdin=b"zz\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn(b"ail diff:", done.stderr)
        report = json.loads(done.stdout.decode("utf-8").splitlines()[-1])
        self.assertEqual(sorted(report), ["cpython", "exit", "line", "native", "outcome", "seconds"])
        self.assertEqual(report["outcome"], "agree")
        self.assertIsNone(report["line"])
        self.assertEqual(report["exit"], [0, 0])
        self.assertEqual(len(report["seconds"]), 2)
        self.assertTrue(all(isinstance(one, (int, float)) for one in report["seconds"]))

    def test_json_shape_on_a_difference(self):
        program = self.write("agree.py", AGREE)
        done = self.ail("run", "--diff", "--json", "--python", self.fake_python(), program, stdin=b"abcdef\n")
        self.assertEqual(done.returncode, 3, done.stderr)
        report = json.loads(done.stdout.decode("utf-8").splitlines()[-1])
        self.assertEqual(report["outcome"], "differ")
        self.assertEqual(report["line"], 1)
        self.assertEqual(report["native"], "read 7")
        self.assertEqual(report["cpython"], "from the fake interpreter")
        self.assertEqual(report["exit"], [0, 0])

    def test_ail_run_without_diff_is_unchanged_and_diff_after_the_source_goes_to_the_program(self):
        program = self.write("agree.py", AGREE)
        done = self.ail("run", program, "--diff", stdin=b"ab\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, b"read 3\narg --diff\n")
        self.assertNotIn(b"ail diff:", done.stderr)

    def test_value_taking_compiler_options_keep_their_value(self):
        # `-I .`, `--syntax python` and `--debug-dir DIR` must reach the build with their value: a
        # dropped value leaves the build with a dangling option and no source file (usage, exit 2).
        program = self.write("agree.py", AGREE)
        for options in (["-I", "."], ["--syntax", "python"], ["--debug-dir", str(self.dir / "debug")]):
            with self.subTest(options=options):
                done = self.ail("run", "--diff", *options, program, stdin=b"ab\n")
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn(b"ail diff: agree", done.stderr)
                self.assertEqual(done.stdout, b"read 3\n")

    def test_bad_options_are_refused(self):
        program = self.write("agree.py", AGREE)
        missing = self.ail("run", "--diff", "--python", self.dir / "does-not-exist", program)
        self.assertEqual(missing.returncode, 2)
        self.assertIn(b"not an executable file", missing.stderr)
        bad_timeout = self.ail("run", "--diff", "--timeout", "soon", program)
        self.assertEqual(bad_timeout.returncode, 2)
        self.assertIn(b"--timeout needs a number", bad_timeout.stderr)


if __name__ == "__main__":
    unittest.main()
