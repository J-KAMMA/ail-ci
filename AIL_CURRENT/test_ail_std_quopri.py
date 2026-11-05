"""quopri1: `import quopri` in compiled programs (bundled stdlib/quopri.py) against CPython's quopri.

The ten programs in lab/stdlib/quopri/ use encodestring/decodestring on plain ASCII, `=`, the
control range 0x00-0x1f, the high range 0x7f-0xff, a round trip of all 256 byte values, quotetabs
True and False with spaces/tabs before a line end and mid-line, header=True (space -> `_`, `_`
quoted), lines of exactly 76 and more than 76 characters (soft `=\n` breaks), soft breaks,
lowercase hex `=3d`, a bad escape `=ZZ`, a trailing `=`, `\r\n` input, and a 5,000-byte input with
`len()` and the first 40 encoded bytes.  Every program is compiled with the default command and
with AIL_UNIFIED_FORCE=1 and run beside `python3` on the same source; stdout and the exit status
must agree.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "quopri"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_ascii_roundtrip.py",
    "02_equals_and_controls.py",
    "03_high_bytes.py",
    "04_all_bytes_roundtrip.py",
    "05_quotetabs.py",
    "06_header.py",
    "07_long_lines.py",
    "08_decode_escapes.py",
    "09_crlf.py",
    "10_large.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibQuopriTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-quopri-test-")
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
