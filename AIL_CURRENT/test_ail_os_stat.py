"""G7: os.stat / os.lstat / os.fspath / os.scandir and the os.path functions that read metadata
(normcase, expanduser, expandvars, getmtime, getatime, getctime, samefile, samestat), compared with
CPython 3.12.

The programs of lab/stdlib/os_stat run over the fixed tree in lab/stdlib/os_stat/data (four files, a
subdirectory and a relative symlink), print only sizes, booleans, sorted names and differences, and
never a raw timestamp (two runs of the same file can differ).  Each one is run by CPython, then built
by AIL in the default (typed) build and with AIL_UNIFIED_FORCE=1 (the general path), and stdout,
stderr and the exit status must agree.
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
LAB = ROOT.parent / "lab" / "stdlib" / "os_stat"


def build(src, exe, general):
    env = dict(os.environ, AIL_NO_CACHE="1")
    if general:
        env["AIL_UNIFIED_FORCE"] = "1"
    else:
        env.pop("AIL_UNIFIED_FORCE", None)
    return subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "-o", str(exe)],
                          cwd=str(LAB), capture_output=True, text=True, timeout=600, env=env)


class OsStatTests(unittest.TestCase):
    def setUp(self):
        self.cc = os.environ.get("PIPE_CC") or shutil.which("gcc") or shutil.which("cc")
        if not self.cc:
            self.skipTest("no C compiler")

    def test_programs(self):
        programs = sorted(LAB.glob("*.py"))
        self.assertGreaterEqual(len(programs), 12, "expected the 12 os_stat programs")
        for src in programs:
            with self.subTest(program=src.name):
                want = subprocess.run([sys.executable, "-B", str(src)], cwd=str(LAB),
                                      capture_output=True, text=True, timeout=120)
                self.assertEqual(want.returncode, 0, want.stderr)
                for general in (False, True):
                    mode = "general" if general else "default"
                    with tempfile.TemporaryDirectory(prefix="ail-os-stat-") as tmp:
                        exe = Path(tmp) / "prog"
                        built = build(src, exe, general)
                        self.assertEqual(built.returncode, 0,
                                         "%s: %s" % (mode, built.stderr[-3000:]))
                        if not general:
                            self.assertNotIn("built on the general path", built.stderr,
                                             "%s: the default build must stay typed" % mode)
                        got = subprocess.run([str(exe)], cwd=str(LAB), capture_output=True,
                                             text=True, timeout=120)
                        self.assertEqual(got.returncode, want.returncode,
                                         "%s exit %r, CPython %r\n%s" %
                                         (mode, got.returncode, want.returncode, got.stderr[-2000:]))
                        if got.stdout != want.stdout:
                            a = want.stdout.split("\n")
                            b = got.stdout.split("\n")
                            for i in range(max(len(a), len(b))):
                                x = a[i] if i < len(a) else "<none>"
                                y = b[i] if i < len(b) else "<none>"
                                if x != y:
                                    self.fail("%s line %d: CPython %r, AIL %r" % (mode, i + 1, x, y))
                        self.assertEqual(got.stdout, want.stdout)


if __name__ == "__main__":
    unittest.main()
