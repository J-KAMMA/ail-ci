"""The realistic `numbers` programs in lab/stdlib/numbers, compared with CPython 3.12.

Eleven of the twelve build in the default mode (on the general path, as the injected ABC
classes use operator methods); each must print CPython's stdout and exit with its status.
The twelfth uses a complex literal, which this runtime does not build, so it stays a named
refusal (see lab/stdlib/numbers/RESULTS.md).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "numbers"

PASSING = (
    "averages.py",
    "classify.py",
    "custom_number.py",
    "dispatch.py",
    "issubclass_report.py",
    "matrix_stats.py",
    "mixed_registry.py",
    "number_guard.py",
    "rationals.py",
    "registration.py",
    "result_kinds.py",
)

REFUSED = {
    "complex_literal.py": "a constant of type complex",
}


def build(directory, name, env=None):
    exe = name[:-3]
    built = subprocess.run(
        [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", name, "--syntax", "python", "-o", exe],
        cwd=directory, capture_output=True, text=True, timeout=900,
        env=dict(os.environ, AIL_NO_CACHE="1", **(env or {})),
    )
    return built, Path(directory, exe)


class NumbersLabTests(unittest.TestCase):
    def test_passing_programs_match_cpython(self):
        for name in PASSING:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                source = Path(directory, name)
                source.write_bytes((LAB / name).read_bytes())
                built, exe = build(directory, name)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=300)
                expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=300)
                self.assertEqual(expected.returncode, 0, expected.stderr)
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                 ran.stderr[:500])

    def test_followups_are_refused_by_name(self):
        for name, wanted in REFUSED.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                Path(directory, name).write_bytes((LAB / name).read_bytes())
                built, exe = build(directory, name)
                self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                self.assertIn(wanted, built.stdout + built.stderr)
                self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
