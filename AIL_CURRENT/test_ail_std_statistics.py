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


def build_source(directory, name, text):
    Path(directory, name).write_text(text, encoding="utf-8")
    exe = name[:-3]
    built = subprocess.run(
        [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", name, "--syntax", "python", "-o", exe],
        cwd=directory, capture_output=True, text=True, timeout=900,
        env=dict(os.environ, AIL_NO_CACHE="1"),
    )
    return built, Path(directory, exe)


def compile_program(directory, name):
    return build_source(directory, name, (LAB / name).read_text(encoding="utf-8"))


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

    def test_weighted_fmean_int_precision(self):
        source = """import statistics


def main() -> None:
    a: list[int] = [9007199254740993, 9007199254740993, 9007199254740993]
    w: list[int] = [1, 1, 1]
    print(statistics.fmean(a, weights=w))
    b: list[int] = [9007199254740993, 9007199254740993, 9007199254740993, 9007199254740993, 9007199254740993]
    print(statistics.fmean(b, weights=[1, 1, 1, 1, 1]))
    one: list[int] = [1, 1, 1]
    print(statistics.fmean(one, weights=[9007199254740993, 9007199254740993, 9007199254740993]))
    p: list[int] = [9007199254740993, 9007199254740993]
    z: list[int] = [9007199254740993, -9007199254740993]
    try:
        print(statistics.fmean(p, weights=z))
    except statistics.StatisticsError as exc:
        print("zero:", exc)


main()
"""
        with tempfile.TemporaryDirectory() as directory:
            built, exe = build_source(directory, "fmean_int.py", source)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=300)
            expected = subprocess.run([sys.executable, str(Path(directory, "fmean_int.py"))],
                                      capture_output=True, timeout=300)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                             ran.stderr[:500])

    def test_computed_correlation_method_is_refused(self):
        source = """import statistics


def main() -> None:
    x: list[int] = [1, 2, 3, 4]
    y: list[int] = [1, 4, 9, 16]
    m: str = "ranked"
    print(statistics.correlation(x, y, method=m))


main()
"""
        with tempfile.TemporaryDirectory() as directory:
            built, exe = build_source(directory, "corr_method.py", source)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn("computed method is not built", built.stderr)
            self.assertFalse(exe.exists())

    def test_followups_are_refused_by_name(self):
        for name, wanted in REFUSED.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_program(directory, name)
                self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                self.assertIn(wanted, built.stderr)
                self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
