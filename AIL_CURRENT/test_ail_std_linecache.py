"""linecache1: `import linecache` in compiled programs (bundled stdlib/linecache.py) against CPython's.

The ten programs in lab/stdlib/linecache/ read the files in `data/` through a path built from
`__file__`, and cover `getline` of the first, a middle and the last line, line numbers 0, a
negative number and one past the end (all `""`), a missing file, a pseudo-filename in angle
brackets, `getlines`, `clearcache`, `checkcache` after the program rewrote the file itself and
after removing it, a file without a final newline, and a UTF-8 file with non-ASCII text.  Every
program is compiled with the default command and with AIL_UNIFIED_FORCE=1 and run beside
`python3` on the same source in the same working directory; stdout and the exit status must
agree.  Both source and `data/` are copied to a temporary directory so a run can never write
into the repository.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "linecache"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_first_line.py",
    "02_middle_line.py",
    "03_last_line.py",
    "04_out_of_range.py",
    "05_missing_file.py",
    "06_getlines.py",
    "07_clearcache.py",
    "08_checkcache_rewrite.py",
    "09_no_final_newline.py",
    "10_utf8.py",
]


def run_cpython(path, cwd):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(cwd),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibLinecacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-linecache-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources], PASSING)
        self.assertTrue((PROGRAMS / "data" / "lines.txt").is_file())
        self.assertTrue((PROGRAMS / "data" / "nonl.txt").is_file())
        self.assertTrue((PROGRAMS / "data" / "utf8.txt").is_file())

    def test_programs_match_cpython(self):
        base = dict(os.environ, AIL_NO_CACHE="1")
        base.pop("PYTHONPATH", None)
        for source in self.sources:
            for mode in ("default", "forced-general"):
                with self.subTest(program=source.name, build=mode):
                    work = self.dir / (source.stem + "-" + mode)
                    work.mkdir(exist_ok=True)
                    program = work / source.name
                    shutil.copyfile(source, program)
                    shutil.copytree(PROGRAMS / "data", work / "data", dirs_exist_ok=True)
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
                    expected = run_cpython(program, work)
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (source.name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, source.name + " " + mode)


if __name__ == "__main__":
    unittest.main()
