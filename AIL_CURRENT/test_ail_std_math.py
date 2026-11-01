"""The lab/stdlib/math programs, compiled in the default mode and compared with CPython 3.12.

Ten of the twelve realistic programs build; each built program must print exactly what CPython
prints and exit with the same status. The two follow-ups stay refused by name (frexp / ldexp and
gamma / lgamma); see lab/stdlib/math/RESULTS.md. A separate precision test compares math.dist
against CPython on both builds, including the last-bit vectors that a naive scaled sum gets wrong.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "math"

DIST_PRECISION = """import math

vectors = [
    ([577446.7022710263, -812280.8264515302, -943305.0469559873, 671530.2078397393, -134465.86418989324],
     [524560.1649158839, -995787.8932977786, -109225.61189039715, 443080.06468156516, -542475.5574590947]),
    ([1e9, -3e9, 5e9, 7e9, -11e9, 13e9, 17e9, 19e9, 23e9, 29e9, 31e9, 37e9, 41e9, 43e9, 47e9, 53e9, 59e9],
     [-2e9, 4e9, -6e9, 8e9, 10e9, -12e9, 14e9, -16e9, 18e9, -20e9, 22e9, -24e9, 26e9, -28e9, 30e9, -32e9, 34e9]),
    ([5e-324, 1e-320, 2.2250738585072014e-308], [0.0, 3e-321, 0.0]),
    ([0.1, 0.2, 0.3, 0.4, 0.5], [0.9, 0.8, 0.7, 0.6, 0.5]),
]
for p, q in vectors:
    print(math.dist(p, q))
"""

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

    def test_dist_precision_matches_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "dist_precision.py")
            source.write_text(DIST_PRECISION)
            want = subprocess.run([sys.executable, "-X", "utf8", str(source)], capture_output=True, timeout=300)
            for mode, forced in (("default", {}), ("general", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(build=mode):
                    exe = Path(directory, "dist_" + mode)
                    env = dict(os.environ, AIL_NO_CACHE="1", **forced)
                    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                                            str(source), "--syntax", "python", "-o", str(exe)],
                                           cwd=directory, capture_output=True, text=True, timeout=1800, env=env)
                    self.assertEqual(built.returncode, 0, "%s\n%s%s"
                                     % (mode, built.stdout[-2000:], built.stderr[-2000:]))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                    self.assertEqual(got.returncode, want.returncode,
                                     "%s exit %s against CPython's %s\n%s"
                                     % (mode, got.returncode, want.returncode,
                                        got.stderr.decode("utf-8", "replace")[-1000:]))
                    self.assertEqual(got.stdout, want.stdout,
                                     "%s stdout differs from CPython\n  compiled: %r\n  CPython:  %r"
                                     % (mode, got.stdout, want.stdout))

    def test_lab_programs_match_cpython(self):
        if not LAB.is_dir():
            self.skipTest("lab/stdlib/math is not present")
        for name in PASSING:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                self.check(name, directory)


if __name__ == "__main__":
    unittest.main()
