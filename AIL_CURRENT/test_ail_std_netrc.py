"""G5a: `import netrc` in compiled programs (bundled stdlib/netrc.py) against CPython's netrc.

The ten programs in lab/stdlib/netrc/ write a netrc file in the current directory and read it
back with netrc.netrc(name): machine/login/password/account and default entries,
authenticators() for known and unknown hosts, macdef blocks, comments, quoted tokens with
backslash escapes, repr(n), NetrcParseError (msg, filename, lineno, str), a missing file and
several hosts.  Each is compiled with the default command and with AIL_UNIFIED_FORCE=1, then
run beside `python3` on the same source; stdout and the exit status must agree.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "netrc"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibNetrcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-netrc-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources],
                         ["01_basic_machine.py", "02_default_entry.py", "03_account_and_hosts.py",
                          "04_macros.py", "05_comments.py", "06_quoted_tokens.py",
                          "07_repr.py", "08_errors.py", "09_missing_file.py",
                          "10_multiple_hosts.py"])

    def test_programs_match_cpython(self):
        base = dict(os.environ, AIL_NO_CACHE="1")
        base.pop("PYTHONPATH", None)
        for mode, forced in (("default", None), ("unified", "1")):
            env = dict(base)
            if forced is None:
                env.pop("AIL_UNIFIED_FORCE", None)
            else:
                env["AIL_UNIFIED_FORCE"] = forced
            for source in self.sources:
                with self.subTest(program=source.name, mode=mode):
                    work = self.dir / (source.stem + "-" + mode)
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
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (source.name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, source.name + " " + mode)


if __name__ == "__main__":
    unittest.main()
