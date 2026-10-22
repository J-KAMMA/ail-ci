"""fuzz38: repr() of a str must use the oracle's str.isprintable() table.

The v2 runtime carries an unprintable code-point table generated from CPython 3.13.6 (Unicode
15.1), while the oracle is CPython 3.12 (Unicode 15.0).  Code points newly assigned in Unicode
15.1 (U+2FFC..U+2FFF, U+31EF, ...) are printable there but not in 3.12, so the default (typed)
build printed the raw character where CPython spells `\\uXXXX`; the general path already adapted
the table to the running Python.  The typed path now does the same.  stdout and the exit status
must match CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''
def show(s: str) -> None:
    print(repr(s), len(repr(s)))


def main() -> None:
    for n in (0x2ffb, 0x2ffc, 0x2ffd, 0x2ffe, 0x2fff, 0x3000, 0x31ef, 0x31f0, 0x378, 0xe000):
        show(chr(n))
    show("\u2ffc\u31ef")


main()
'''


class Fuzz38(unittest.TestCase):
    def test_repr_uses_the_running_cpython_printability_table(self):
        with tempfile.TemporaryDirectory(prefix="ail-fuzz38-") as directory:
            d = Path(directory)
            src = d / "p.py"
            src.write_text(PROGRAM, encoding="utf-8")
            want = subprocess.run([sys.executable, "-B", str(src)], capture_output=True, timeout=120)
            self.assertEqual(want.returncode, 0, want.stderr.decode("utf-8", "replace"))
            for general in (True, False):
                env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
                env.pop("AIL_UNIFIED_FORCE", None)
                if general:
                    env["AIL_UNIFIED_FORCE"] = "1"
                exe = d / ("exe_g" if general else "exe_d")
                built = subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "--syntax", "python",
                                        "-o", str(exe)], cwd=d, capture_output=True, text=True, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120)
                self.assertEqual(got.stdout, want.stdout, "general" if general else "default")
                self.assertEqual(got.returncode, want.returncode)


if __name__ == "__main__":
    unittest.main()
