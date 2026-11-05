"""nturl2path1: `import nturl2path` in compiled programs (bundled stdlib/nturl2path.py) against CPython.

The ten programs in lab/stdlib/nturl2path/ cover `url2pathname` (drive forms with `|` and `:`,
UNC forms with two to four leading slashes, relative and empty URLs, percent escapes including
`%20`, `%C3%A9` and a bad `%zz`) and `pathname2url` (drive forms, `C:`, UNC, the `\\\\?\\` and
`\\\\?\\UNC\\` prefixes, relative paths, spaces and non-ASCII letters), each `OSError` CPython
raises (`Bad URL: ...`, `Bad path: ...`, caught and printed as `str(e)`), and a round trip
`url2pathname(pathname2url(p)) == p` over eight paths.  Every program is compiled with the default
command and with AIL_UNIFIED_FORCE=1 and run beside `python3` on the same source; stdout and the
exit status must agree.

The module carries its own percent codec: urllib is built on the typed path only, so a program
built with AIL_UNIFIED_FORCE=1 refuses `import urllib.parse`.  The typed-only build
(AIL_NO_GENERAL=1) is not built because it has no `ord()`.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "nturl2path"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_url2pathname_drive.py",
    "02_url2pathname_unc.py",
    "03_url2pathname_relative.py",
    "04_url2pathname_escapes.py",
    "05_pathname2url_drive.py",
    "06_pathname2url_unc.py",
    "07_pathname2url_relative.py",
    "08_errors_url.py",
    "09_errors_path.py",
    "10_roundtrip.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibNturl2pathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-nturl2path-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources], PASSING)
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
