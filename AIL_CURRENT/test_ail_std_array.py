"""The lab/stdlib/array programs that build, compiled and compared with CPython 3.12.

Nine of the twelve realistic programs build on the general path (the array prelude is Python source);
the other three are refused by name in lab/stdlib/array/RESULTS.md: float32 ('f'), unicode ('u') and
tobytes/frombytes/buffer_info. Each built program must print exactly what CPython prints and exit
with the same status on both AIL_IR modes.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "array"

PROGRAMS = (
    "audio_frames",
    "constructor_forms",
    "error_edges",
    "histogram",
    "inventory",
    "matrix_rows",
    "ring_buffer",
    "rolling_mean",
    "sensor_compare",
)


class StdArray(unittest.TestCase):
    def check(self, name, ir, directory):
        source = LAB / (name + ".py")
        exe = Path(directory, name + "_" + ir)
        env = dict(os.environ, AIL_IR=ir, AIL_NO_CACHE="1")
        env.pop("AIL_NO_GENERAL", None)
        env.pop("AIL_UNIFIED_FORCE", None)
        built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                                "--syntax", "python", "-o", str(exe)], cwd=directory, capture_output=True,
                               text=True, timeout=1800, env=env)
        self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s"
                         % (name, ir, built.stdout[-2000:], built.stderr[-2000:]))
        want = subprocess.run([sys.executable, "-X", "utf8", str(source)], capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], capture_output=True, timeout=300)
        self.assertEqual(got.returncode, want.returncode,
                         "%s (AIL_IR=%s) exit %s against CPython's %s\n%s"
                         % (name, ir, got.returncode, want.returncode,
                            got.stderr.decode("utf-8", "replace")[-1000:]))
        if got.stdout != want.stdout:
            expected = want.stdout.decode("utf-8", "replace").splitlines()
            actual = got.stdout.decode("utf-8", "replace").splitlines()
            for line, (a, b) in enumerate(zip(actual, expected), 1):
                if a != b:
                    self.fail("%s (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                              % (name, ir, line, a, b))
            self.fail("%s (AIL_IR=%s): %d lines against %d" % (name, ir, len(actual), len(expected)))

    def test_lab_programs_match_cpython(self):
        if not LAB.is_dir():
            self.skipTest("lab/stdlib/array is not present")
        self.assertGreaterEqual(len(PROGRAMS), 9)
        for name in PROGRAMS:
            for ir in ("0", "1"):
                with self.subTest(program=name, ir=ir), tempfile.TemporaryDirectory() as directory:
                    self.check(name, ir, directory)


if __name__ == "__main__":
    unittest.main()
