"""The CPython `pprint` module in compiled programs: the lab/stdlib/pprint programs against CPython 3.12.

Each program is ordinary Python. CPython runs it as the oracle; the compiled program prints the same
bytes and exits with the same status. The default build and AIL_IR=1 are both checked.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "pprint"


def compile_python(directory, source, name, **env):
    exe = Path(directory, name)
    built = subprocess.run(
        [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source),
         "--syntax", "python", "-o", str(exe)],
        cwd=directory, capture_output=True, text=True, timeout=1800,
        env=dict(os.environ, **env))
    return built, exe


class PprintPrograms(unittest.TestCase):
    def check(self, source, ir):
        name = source.stem + ("_ir" if ir else "")
        with tempfile.TemporaryDirectory() as directory:
            env = {"AIL_IR": "1"} if ir else {}
            built, exe = compile_python(directory, source, name, **env)
            self.assertEqual(built.returncode, 0, "%s\n%s%s" % (source.name, built.stdout, built.stderr))
            want = subprocess.run([sys.executable, "-X", "utf8", str(source)],
                                  capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode,
                             "%s: %s" % (source.name, got.stderr[-500:].decode(errors="replace")))
            if got.stdout != want.stdout:
                a = got.stdout.decode(errors="replace").splitlines()
                b = want.stdout.decode(errors="replace").splitlines()
                for n, (x, y) in enumerate(zip(a, b)):
                    if x != y:
                        self.fail("%s line %d:\n  compiled: %r\n  CPython:  %r"
                                  % (source.name, n + 1, x, y))
                self.fail("%s: %d lines against %d" % (source.name, len(a), len(b)))

    def test_programs_match_cpython(self):
        sources = sorted(PROGRAMS.glob("p*.py"))
        self.assertGreaterEqual(len(sources), 12)
        for source in sources:
            for ir in (False, True):
                with self.subTest(program=source.name, ir=ir):
                    self.check(source, ir)


if __name__ == "__main__":
    unittest.main()
