"""The statistics programs of lab/stdlib/statistics: each passing program is compiled in the default mode and
must print what CPython prints (stdout and exit code).

The two follow-ups stay refused by name until their features are built: linear_regression (the named tuple
result and proportional=) and NormalDist (the distribution class).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "statistics"

PASSING = (
    "01_score_summary.py",
    "02_modes.py",
    "03_string_modes.py",
    "04_float_stats.py",
    "05_quantiles_report.py",
    "06_covariance_correlation.py",
    "09_weighted_stats.py",
    "10_grouped_stats.py",
    "11_geometric_harmonic.py",
    "12_error_handling.py",
)

REFUSED = {
    "07_regression.py": "statistics.linear_regression",
    "08_normal_dist.py": "statistics.NormalDist",
}


def compile_program(directory, name):
    source = Path(directory, name)
    source.write_text((LAB / name).read_text(encoding="utf-8"), encoding="utf-8")
    exe = name[:-3]
    built = subprocess.run(
        [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", name, "--syntax", "python", "-o", exe],
        cwd=directory, capture_output=True, text=True, timeout=900,
        env=dict(os.environ, AIL_NO_CACHE="1"),
    )
    return built, Path(directory, exe)


class StatisticsLabTests(unittest.TestCase):
    def test_passing_programs_match_cpython(self):
        for name in PASSING:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_program(directory, name)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=300)
                expected = subprocess.run([sys.executable, str(LAB / name)], capture_output=True, timeout=300)
                self.assertEqual(expected.returncode, 0, expected.stderr)
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                 ran.stderr[:500])

    def test_followups_are_refused_by_name(self):
        for name, wanted in REFUSED.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_program(directory, name)
                self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                self.assertIn(wanted, built.stderr)
                self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
