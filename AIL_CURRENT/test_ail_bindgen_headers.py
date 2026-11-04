"""bindgen1: `ail_bindgen.py --cpp` on the installed zlib.h and math.h, through two examples.

`examples/ffi/bindgen/zlib_gen.py` and `libm_gen.py` import the committed modules of generated
stubs (`zlib_gen_ffi.py`, `math_gen_ffi.py`, each with the command that made it in its first line)
and print what they compute. Each example runs under `python3` (the ctypes shim in ail_ffi.py) and
as the executable `ail_chatgpt.py compile` builds from the same files; stdout and the exit status
must be equal.

The last two tests re-run the generator on the real header and check that every function the
examples call still gets a stub. An example is skipped, with the missing header, library or
compiler named in the reason, when the runner does not have it.
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
BINDGEN = str(ROOT / "ail_bindgen.py")
EXAMPLES = REPO / "examples" / "ffi" / "bindgen"
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


def missing(header, lib):
    if not CC:
        return "installed C compiler required"
    if not have_header(header):
        return "%s is not installed" % header
    if not have_lib(lib):
        return "-l%s is not installed" % lib
    return None


class BindgenHeaderTests(unittest.TestCase):
    def compare(self, name, module):
        source = EXAMPLES / name
        self.assertTrue(source.is_file(), source)
        self.assertTrue((EXAMPLES / module).is_file(), module)
        with tempfile.TemporaryDirectory(prefix="ail-bindgen-example-") as directory:
            work = Path(directory)
            for file in (name, module):
                shutil.copyfile(EXAMPLES / file, work / file)
            env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
            expected = subprocess.run([sys.executable, "-B", str(work / name)], cwd=work,
                                      capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            exe = work / (name[:-3] + ".out")
            built = subprocess.run([sys.executable, "-B", CLI, "compile", str(work / name), "-o", str(exe)],
                                   cwd=work, capture_output=True, text=True, timeout=600,
                                   env=dict(env, AIL_NO_CACHE="1"))
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertNotIn("built on the general path", built.stderr)
            ran = subprocess.run([str(exe)], cwd=work, capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(ran.returncode, expected.returncode, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            self.assertEqual(ran.stderr, expected.stderr)
            return ran.stdout

    def generated(self, header, lib):
        done = subprocess.run([sys.executable, "-B", BINDGEN, header, "--cpp", "--header-name",
                               Path(header).name, "--link", lib], capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def test_zlib_generated_stubs(self):
        reason = missing("zlib.h", "z")
        if reason:
            self.skipTest(reason)
        out = self.compare("zlib_gen.py", "zlib_gen_ffi.py")
        self.assertEqual(out.splitlines()[0], "zlib 1")

    def test_libm_generated_stubs(self):
        reason = missing("math.h", "m")
        if reason:
            self.skipTest(reason)
        out = self.compare("libm_gen.py", "math_gen_ffi.py")
        self.assertEqual(len(out.splitlines()), 8)

    def test_generator_covers_zlib_example(self):
        reason = missing("zlib.h", "z")
        if reason:
            self.skipTest(reason)
        stubs = self.generated("/usr/include/zlib.h", "z")
        for name in ("zlibVersion", "crc32", "adler32", "compressBound", "compress2", "uncompress"):
            self.assertIn("def %s(" % name, stubs)

    def test_generator_covers_libm_example(self):
        reason = missing("math.h", "m")
        if reason:
            self.skipTest(reason)
        stubs = self.generated("/usr/include/math.h", "m")
        for name in ("sin", "cos", "tan", "exp", "log", "fabs", "sqrt", "fma", "pow"):
            self.assertIn("def %s(" % name, stubs)


if __name__ == "__main__":
    unittest.main()
