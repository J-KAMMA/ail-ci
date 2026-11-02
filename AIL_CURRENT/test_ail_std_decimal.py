"""The 12 real `decimal` programs in lab/stdlib/decimal, against CPython 3.12.

Each source is copied into a temporary directory, built with the default command
(`compile X.py --syntax python`, so the typed path may fall back to the general path)
and run with the same (empty) stdin as CPython.  stdout and the exit code must be identical.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "decimal"


def cases():
    return {path.stem: path for path in sorted(PROGRAMS.glob("*.py"))}


class DecimalPrograms(unittest.TestCase):
    def test_lab_programs_match_cpython(self):
        found = cases()
        self.assertEqual(len(found), 12, sorted(found))
        for stem, source in found.items():
            with self.subTest(program=stem), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                src = directory / (stem + ".py")
                src.write_bytes(source.read_bytes())
                exe = directory / "exe"
                built = subprocess.run(
                    [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", src.name,
                     "--syntax", "python", "-o", exe.name],
                    cwd=directory, capture_output=True, text=True, timeout=900,
                    env=dict(os.environ, AIL_NO_CACHE="1"))
                self.assertEqual(built.returncode, 0,
                                 "%s did not build:\n%s\n%s" % (stem, built.stdout, built.stderr))
                want = subprocess.run([sys.executable, "-B", src.name], cwd=directory,
                                      capture_output=True, timeout=120)
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                self.assertEqual(
                    (got.returncode, got.stdout), (want.returncode, want.stdout),
                    "%s\nexit %r != %r\nstderr:\n%s" % (
                        stem, got.returncode, want.returncode,
                        got.stderr.decode("utf-8", "replace")))


if __name__ == "__main__":
    unittest.main()
