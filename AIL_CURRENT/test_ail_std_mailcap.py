"""mailcap1: `import mailcap` in compiled programs (bundled stdlib/mailcap.py) against CPython's mailcap.

The ten programs in lab/stdlib/mailcap/ write a mailcap text to a file in the current directory and
read it back with `mailcap.getcaps()` after setting MAILCAPS, or with `mailcap.readmailcapfile`.
Together they use comments, blank lines, continuation lines ending in a backslash, key=value and
flag fields, the `lineno` key, `lookup` for an exact type, a `text/*` wildcard and a missing type,
`findmatch` for entries without a `test=` field (with and without a plist), `subst` with `%s`, `%t`,
`%{charset}`, `%%` and a backslash escape, and an unsafe filename (`"a;rm"`), where findmatch
returns (None, None).  Every program is compiled with the default command and with
AIL_UNIFIED_FORCE=1 and run beside `python3` on the same source; stdout and the exit status must
agree.

CPython 3.12 prints a DeprecationWarning for `import mailcap`; only stdout and the exit status are
compared.  CPython's `readmailcapfile` and `UnsafeMailcapInput` messages also go to stderr; the
bundled module writes the same text there, because the compiler does not build `warnings`.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "mailcap"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_parse_basic.py",
    "02_continuation.py",
    "03_lineno.py",
    "04_lookup_plain.py",
    "05_lookup_wildcard.py",
    "06_missing_type.py",
    "07_findmatch_no_test.py",
    "08_findmatch_plist.py",
    "09_subst_direct.py",
    "10_unsafe_filename.py",
]


def run_cpython(path, cwd):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(cwd),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibMailcapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-mailcap-test-")
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
                    expected = run_cpython(source, work)
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (source.name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, source.name + " " + mode)


if __name__ == "__main__":
    unittest.main()
