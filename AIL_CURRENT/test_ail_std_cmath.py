"""The twelve real `cmath` programs in lab/stdlib/cmath, against CPython 3.12.

Each source is copied into a temporary directory, built with the default command
(`compile X.py --syntax python`, so the typed path may fall back to the general path) and run;
stdout and the exit code must be identical to CPython's.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "cmath"

PROGRAMS = (
    "branch_cuts.py",
    "error_handling.py",
    "filter_response.py",
    "impedance.py",
    "inverse_trig.py",
    "log_transform.py",
    "mandelbrot.py",
    "phasors.py",
    "quadratic.py",
    "rotation.py",
    "trig_identities.py",
    "wave_superposition.py",
)


class CmathLabTests(unittest.TestCase):
    def test_programs_match_cpython(self):
        for name in PROGRAMS:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                source = Path(directory, name)
                source.write_text((LAB / name).read_text(encoding="utf-8"), encoding="utf-8")
                exe = name[:-3]
                built = subprocess.run(
                    [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", name,
                     "--syntax", "python", "-o", exe],
                    cwd=directory, capture_output=True, text=True, timeout=900,
                    env=dict(os.environ, AIL_NO_CACHE="1"))
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(Path(directory, exe))], cwd=directory,
                                     capture_output=True, timeout=300)
                expected = subprocess.run([sys.executable, name], cwd=directory,
                                          capture_output=True, timeout=300)
                self.assertEqual((ran.returncode, ran.stdout),
                                 (expected.returncode, expected.stdout), ran.stderr[:500])


if __name__ == "__main__":
    unittest.main()
