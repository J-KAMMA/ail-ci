"""The lab/stdlib/math programs, compiled in the default mode and compared with CPython 3.12.

Ten of the twelve realistic programs build; each built program must print exactly what CPython
prints and exit with the same status. The two follow-ups stay refused by name (frexp / ldexp and
gamma / lgamma); see lab/stdlib/math/RESULTS.md.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "math"

PASSING = (
    "circle_pack",
    "compound_growth",
    "distance_report",
    "floating_edges",
    "normal_probability",
    "number_theory",
    "prime_report",
    "projectile",
    "statistics_summary",
    "wave_samples",
)


class StdMath(unittest.TestCase):
    def check(self, name, directory):
        source = LAB / (name + ".py")
        exe = Path(directory, name)
        built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                                "--syntax", "python", "-o", str(exe)], cwd=directory, capture_output=True,
                               text=True, timeout=1800, env=dict(os.environ, AIL_NO_CACHE="1"))
        self.assertEqual(built.returncode, 0, "%s\n%s%s"
                         % (name, built.stdout[-2000:], built.stderr[-2000:]))
        want = subprocess.run([sys.executable, "-X", "utf8", str(source)], capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], capture_output=True, timeout=300)
        self.assertEqual(got.returncode, want.returncode,
                         "%s exit %s against CPython's %s\n%s"
                         % (name, got.returncode, want.returncode,
                            got.stderr.decode("utf-8", "replace")[-1000:]))
        if got.stdout != want.stdout:
            expected = want.stdout.decode("utf-8", "replace").splitlines()
            actual = got.stdout.decode("utf-8", "replace").splitlines()
            for line, (a, b) in enumerate(zip(actual, expected), 1):
                if a != b:
                    self.fail("%s line %d:\n  compiled: %r\n  CPython:  %r" % (name, line, a, b))
            self.fail("%s: %d lines against %d" % (name, len(actual), len(expected)))

    def test_lab_programs_match_cpython(self):
        if not LAB.is_dir():
            self.skipTest("lab/stdlib/math is not present")
        for name in PASSING:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                self.check(name, directory)


if __name__ == "__main__":
    unittest.main()
