"""The stdlib `struct` programs in lab/stdlib/struct, compared with CPython 3.12.

Each program is built by the default command (`ail_chatgpt.py compile X.py --syntax python`); the typed path
names the prelude's module-level format tables, so the build falls back to the general path, which is the
result recorded in lab/stdlib/struct/RESULTS.md.  stdout and the exit code must match CPython exactly.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "struct"


class StructPrograms(unittest.TestCase):
    def compare(self, program):
        text = program.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            source, exe = Path(directory, program.name), Path(directory, program.stem)
            source.write_text(text, encoding="utf-8")
            built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                                    "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                                   text=True, timeout=1800, env=dict(os.environ, AIL_NO_CACHE="1"))
            self.assertEqual(built.returncode, 0, "%s\n%s%s" % (
                program.name, built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], cwd=directory,
                                  capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s\n%s" % (
                program.name, got.stderr.decode("utf-8", "replace")))
            if got.stdout != want.stdout:
                want_lines, got_lines = want.stdout.decode("utf-8", "replace").splitlines(), \
                    got.stdout.decode("utf-8", "replace").splitlines()
                for line, (a, b) in enumerate(zip(want_lines, got_lines), 1):
                    if a != b:
                        self.fail("%s line %d:\n  compiled: %r\n  CPython:  %r" % (program.name, line, b, a))
                self.fail("%s: output lengths differ" % program.name)

    def test_programs(self):
        programs = sorted(PROGRAMS.glob("*.py"))
        self.assertEqual(len(programs), 12)
        for program in programs:
            with self.subTest(program=program.name):
                self.compare(program)


if __name__ == "__main__":
    unittest.main()
