"""P4: the user-facing FFI examples in `examples/ffi/`, each checked against CPython.

Each example is a whole program against a real system library: zlib, libm, libc and sqlite3. It runs under
`python3` (the ctypes shim in ail_ffi.py) and as the executable `ail_chatgpt.py compile` builds from the same
file. The stdout and the exit status must be equal. An example is skipped, with the missing header or library
named in the reason, when the runner does not have it.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = str(ROOT / "ail_chatgpt.py")
EXAMPLES = REPO / "examples" / "ffi"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")


def have_header(name):
    if not CC:
        return False
    done = subprocess.run([CC, "-E", "-x", "c", "-", "-o", os.devnull], input="#include <%s>\n" % name,
                          capture_output=True, text=True)
    return done.returncode == 0


def have_lib(name):
    if not CC:
        return False
    done = subprocess.run([CC, "-x", "c", "-", "-l" + name, "-o", os.devnull],
                          input="int main(void){return 0;}\n", capture_output=True, text=True)
    return done.returncode == 0


def missing(headers=(), libs=()):
    if not CC:
        return "installed C compiler required"
    for name in headers:
        if not have_header(name):
            return "%s is not installed" % name
    for name in libs:
        if not have_lib(name):
            return "-l%s is not installed" % name
    return None


class FFIExampleTests(unittest.TestCase):
    def compare(self, name):
        source = EXAMPLES / name
        self.assertTrue(source.is_file(), source)
        with tempfile.TemporaryDirectory(prefix="ail-ffi-example-") as directory:
            work = Path(directory)
            local = work / name
            shutil.copyfile(source, local)
            env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
            expected = subprocess.run([sys.executable, "-B", str(local)], cwd=work, capture_output=True,
                                      text=True, timeout=120, env=env)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            exe = work / (name[:-3] + ".out")
            built = subprocess.run([sys.executable, "-B", CLI, "compile", str(local), "-o", str(exe)],
                                   cwd=work, capture_output=True, text=True, timeout=600,
                                   env=dict(env, AIL_NO_CACHE="1"))
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(exe)], cwd=work, capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(ran.returncode, expected.returncode, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            self.assertEqual(ran.stderr, expected.stderr)
            return ran.stdout

    def test_zlib_check(self):
        reason = missing(["zlib.h"], ["z"])
        if reason:
            self.skipTest(reason)
        out = self.compare("zlib_check.py")
        self.assertIn("round trip ok\n", out)
        self.assertEqual(len(out.splitlines()), 4)

    def test_libm_math(self):
        reason = missing(["math.h"], ["m"])
        if reason:
            self.skipTest(reason)
        out = self.compare("libm_math.py")
        self.assertEqual(len(out.splitlines()), 6)
        self.assertIn("inf", out)
        self.assertIn("5e-324", out)
        self.assertIn("-0.0", out)

    def test_libc_text(self):
        reason = missing(["string.h", "stdlib.h", "ctype.h"])
        if reason:
            self.skipTest(reason)
        out = self.compare("libc_text.py")
        self.assertIn("9223372036854775807", out)
        self.assertIn("4738381338321616895", out)
        self.assertIn("MIXED CASE 123\n", out)
        self.assertIn("Numerical result out of range", out)

    def test_sqlite_count(self):
        reason = missing(["sqlite3.h"], ["sqlite3"])
        if reason:
            self.skipTest(reason)
        out = self.compare("sqlite_count.py")
        self.assertEqual(out, "1000 500500\n")


if __name__ == "__main__":
    unittest.main()
