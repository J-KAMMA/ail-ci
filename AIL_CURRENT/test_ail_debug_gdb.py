"""`--debug` builds under gdb: the matrix and the DWARF line coverage of lab/debug (lab/debug/RESULTS.md).

* linecov: every executable statement line of 4 typed-path programs is in the DWARF line table of their
  `--debug` build (readelf), and the general-path program's lines are too;
* the gdb matrix (`gdb -batch -x script`): break at a line, `next` five times against the lines CPython's
  sys.settrace visits, `bt` 3 calls deep, `finish`, `info locals` and `print` of int and float locals by their
  Python names, an IndexError stopped in the runtime's `ail_die`, a breakpoint in an imported module. The
  checks known to fail (RESULTS.md, "After") are listed in KNOWN and must stay the only failures (a fixed one
  may leave the list).

Prints `gdb: <version>` first (or that gdb is missing) so a CI log shows whether the gdb checks ran. Skipped
only without a C compiler, readelf (the line coverage) or gdb (the matrix).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "debug"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
GDB = shutil.which("gdb")

sys.path.insert(0, str(LAB))
import linecov  # noqa: E402

# the 4 programs of the line-coverage check (typed path), and the general-path one
TYPED = ("p01_loops.py", "p05_try.py", "p06_import.py", "p08_locals.py")
GENERAL = "p07_general.py"
# the matrix's failures recorded in RESULTS.md, with the file that has to change to fix each
KNOWN = {
    "next x5 p05_try.py:2",                            # the try body is outlined into another C function
    "next x5 p10_strings.py:9",                        # pyfunc.py: one #line for a statement over 3 C lines
    "finish from inner returns to middle:7 with 11",   # pyfunc.py: always_inline in debug builds
    # the IR path's locals are SSA values (`ir1`) and parameters `v_n`: no C variable has the Python name, and
    # test_ail_debug_lines pins a debug build's C to the release C plus #line and site lines
    "info locals names k, g, r", "print n == 42", "print f == 1.5", "print k == 43", "print g == 3",
}

if GDB:
    print("gdb: " + subprocess.run([GDB, "--version"], capture_output=True, text=True).stdout.splitlines()[0])
else:
    print("gdb: not installed, the gdb matrix is skipped")
sys.stdout.flush()


@unittest.skipUnless(CC, "no C compiler")
class DebugGdb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-debug-gdb-")
        self.addCleanup(self.tmp.cleanup)

    @unittest.skipUnless(shutil.which("readelf"), "no readelf")
    def test_every_statement_line_is_in_the_line_table(self):
        for name in TYPED:
            for f, path, want, missing, _ in linecov.measure(LAB / "progs" / name, False, self.tmp.name):
                self.assertEqual(path, "typed", f)
                self.assertEqual(missing, [], "%s: statement lines missing from the line table" % f)
                self.assertTrue(want, f)

    @unittest.skipUnless(shutil.which("readelf"), "no readelf")
    def test_general_path_lines(self):
        for f, path, want, missing, _ in linecov.measure(LAB / "progs" / GENERAL, True, self.tmp.name):
            self.assertEqual(path, "general", f)
            self.assertEqual(missing, [], f)

    @unittest.skipUnless(GDB, "gdb is not installed")
    def test_gdb_matrix(self):
        checks = linecov.matrix(self.tmp.name)
        for name, ok, detail in checks:
            print("  %-4s %-55s %s" % ("ok" if ok else "FAIL", name, detail))
        self.assertEqual(len(checks), 30)
        failed = {name for name, ok, _ in checks if not ok}
        self.assertEqual(failed - KNOWN, set(), "new gdb failures")
        print("  gdb checks %d/30 (RESULTS.md: %d recorded failures)" % (30 - len(failed), len(KNOWN)))


if __name__ == "__main__":
    unittest.main()
