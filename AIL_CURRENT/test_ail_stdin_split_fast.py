"""`input()` + `split()` + `int(f[k])` on stdin: the fast paths match CPython at the edges.

A `for`/`while` loop over stdin lines with `line.split()` and `int(...)` now keeps the line
block out of the arena slow path, splits an ASCII line with a word-at-a-time field scan, and
parses the common 1..18 digit token inline.  The cases below are the boundaries those shortcuts
imply: tabs, CRLF, blank lines, a missing final newline, more than 32 fields, the non-ASCII
spaces U+3000 (whitespace) and U+00A0 (not whitespace), invalid UTF-8, EOF in the loop, the int
spellings `-0` / `+5` / `007`, 18/19/20 digit values, the int64 edges, and 2**70 in the default
build (a loud stop) and with `--exact-int` (exact, as CPython).  Every program is built on the
default and the forced-general path and run without a cache.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AIL = ROOT / "ail_chatgpt.py"

SPLIT = '''import sys


def main():
    n = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        f = line.split()
        print(len(f), "|".join(f))
        n += 1
    print("lines", n)


main()
'''

INT = '''import sys


def main():
    while True:
        try:
            line = input()
        except EOFError:
            break
        for tok in line.split():
            try:
                print(tok, int(tok))
            except ValueError:
                print(tok, "ValueError")
    print("done")


main()
'''

SPLIT_INPUT = (
    b"a\tb  c\n"
    b"  lead and trail  \n"
    b"\n"
    b"   \n"
    b"one\r\n"
    b"many " + b" ".join(str(i).encode() for i in range(40)) + b"\n"
    + "wide\u3000space nbsp\u00a0here\n".encode("utf-8")
    + b"\x1c\x1d\x1e\x1fsep\n"
)

NO_FINAL_NEWLINE = b"last  line no newline"

INT_SAFE = "\n".join([
    "-0", "+5", "007", "0", "-7",
    "123456789012345678", "999999999999999999",
    "00000000000000000042", "9223372036854775807", "-9223372036854775808",
    "  42  ",
]) + "\n"

INT_OVERFLOW = [
    "9223372036854775808",
    "-9223372036854775809",
    "10000000000000000000",
]

TWO70 = "1180591620717411303424\n"


def build(directory, text, name, exact=False):
    source = Path(directory) / (name + ".py")
    source.write_text(text)
    exe = Path(directory) / name
    cmd = [sys.executable, str(AIL), "compile", str(source), "--syntax", "python",
           "-o", str(exe)]
    if exact:
        cmd.append("--exact-int")
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_SERVER="0")
    built = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    return built, exe


def run(exe, data, env=None):
    return subprocess.run([str(exe)], input=data, capture_output=True, timeout=120,
                          env=env)


class StdinSplitFastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        d = cls._tmp.name
        cls.exes = {}
        for mode, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
            env = dict(os.environ, **extra)
            for name, text in (("split", SPLIT), ("int", INT)):
                built, exe = build(d, text, name + "_" + mode)
                if built.returncode != 0:
                    raise RuntimeError(built.stdout + built.stderr)
                cls.exes[(name, mode)] = (exe, env)
            built, exe = build(d, INT, "exact_" + mode, exact=True)
            if built.returncode != 0:
                raise RuntimeError(built.stdout + built.stderr)
            cls.exes[("exact", mode)] = (exe, env)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def check_cpython(self, program, data, name):
        expected = subprocess.run([sys.executable, "-c", program], input=data,
                                  capture_output=True, timeout=120)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        for mode in ("default", "unified"):
            exe, env = self.exes[(name, mode)]
            got = run(exe, data, env)
            with self.subTest(program=name, mode=mode):
                self.assertEqual(got.returncode, 0, got.stderr)
                self.assertEqual(got.stdout, expected.stdout)

    def test_split_and_input_match_cpython(self):
        for data in (SPLIT_INPUT, NO_FINAL_NEWLINE):
            self.check_cpython(SPLIT, data, "split")

    def test_empty_input_stops_on_eof(self):
        self.check_cpython(SPLIT, b"", "split")

    def test_invalid_utf8_stops_after_the_valid_prefix(self):
        data = b"abc\n\xff\xfe\nxyz\n"
        # CPython's default stdin uses surrogateescape and keeps going; AIL's str cannot hold a
        # lone surrogate, so the documented difference C?-diffs3-3 is the strict-mode text and
        # exit 1.  CPython in strict mode can fail during its read-ahead before the first line,
        # so the stable part to compare is the valid prefix AIL already printed.
        for mode in ("default", "unified"):
            exe, env = self.exes[("split", mode)]
            got = run(exe, data, env)
            with self.subTest(mode=mode):
                self.assertEqual(got.returncode, 1)
                self.assertEqual(got.stdout, b"1 abc\n")
                self.assertIn(b"UnicodeDecodeError", got.stderr)

    def test_int64_safe_values_match_cpython(self):
        self.check_cpython(INT, INT_SAFE.encode(), "int")

    def test_int64_overflow_stops_loudly(self):
        for value in INT_OVERFLOW:
            for mode in ("default", "unified"):
                exe, env = self.exes[("int", mode)]
                got = run(exe, (value + "\n").encode(), env)
                with self.subTest(value=value, mode=mode):
                    self.assertEqual(got.returncode, 1)
                    self.assertEqual(got.stdout, b"")
                    self.assertIn(b"OverflowError: integer overflow in int()", got.stderr)

    def test_two_to_70_is_exact_with_exact_int(self):
        expected = subprocess.run([sys.executable, "-c", INT], input=TWO70.encode(),
                                  capture_output=True, timeout=120)
        self.assertEqual(expected.returncode, 0)
        for mode in ("default", "unified"):
            exe, env = self.exes[("exact", mode)]
            got = run(exe, TWO70.encode(), env)
            with self.subTest(mode=mode):
                self.assertEqual(got.returncode, 0, got.stderr)
                self.assertEqual(got.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()
