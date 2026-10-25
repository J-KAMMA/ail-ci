"""Encoding names are matched the way CPython matches them (job pre23).

`encodings.normalize_encoding` replaces punctuation runs with one underscore and drops leading and
trailing punctuation, so `utf\t8`, `utf 8`, `UTF_8` and ` utf-8 ` all name UTF-8, and
`iso-8859-1:1987` names Latin-1. The bytes prelude and the general path's literal-codec check now
use that normalization instead of only replacing spaces and underscores. Unsupported names still
raise LookupError at run time (a literal one may still be refused at compile time, by name).

The names reach encode/decode through an argument, a list item, an attribute and a dict value, as
well as literals, on the default and IR builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LITERALS = r"""def main():
    print(repr(b"abc".decode("utf\t8")))
    print(repr(b"abc".decode("iso-8859-1:1987")))
    print(repr(b"abc".decode("UTF_8")))
    print(repr(b"abc".decode(" utf 8 ")))
    print(repr("abc".encode("utf\t8")))
    print(repr("abc".encode("iso-8859-1:1987")))
    print(repr(bytes("abc", "iso-8859-1:1987")))
    print(repr(str(b"\xe9", "ISO\t8859-1")))
    print(repr(b"".decode("utf\t8")))
    print(repr("".encode("iso-8859-1:1987")))
    print(repr(bytearray(b"abc").decode("iso-8859-1:1987")))


main()
"""

NAMES = r"""class Holder:
    def __init__(self, name):
        self.name = name


def dec(name):
    return b"abc".decode(name)


def enc(name):
    return "abc".encode(name)


def main():
    names = ["utf\t8", "iso-8859-1:1987", "UTF_8", " utf 8 ", "iso_8859_1:1987", "iso\t8859\t1",
             "utf\n8", "utf\r\n8", "utf\v8", "utf\f8", "utf8\n", "ISO-8859-1:1987\n",
             "utf8_ucs2", "utf8_ucs4", "csisolatin1", "iso8859", "ansi_x3.4_1986",
             "iso_646.irv_1991", "csascii", "cp367", "iso-ir-100"]
    for name in names:
        print(repr(dec(name)), repr(enc(name)))
    d = {"k": "utf\t8"}
    print(repr(dec(d["k"])), repr(enc(d["k"])))
    xs = ["iso-8859-1:1987"]
    print(repr(dec(xs[0])), repr(enc(xs[0])))
    h = Holder("UTF\t8")
    print(repr(dec(h.name)), repr(enc(h.name)))
    print(repr(bytes("abc", xs[0])), repr(str(b"\xe9", "ISO\t8859-1")))
    print(repr(bytearray(b"abc").decode("iso-8859-1:1987")))
    print(repr(b"".decode("utf\t8")), repr("".encode("iso-8859-1:1987")))
    for name in ["utf\t9", "iso-8859-1:1988", "", "bad"]:
        try:
            print(repr(b"abc".decode(name)))
        except Exception as exc:
            print(type(exc).__name__, str(exc))
        try:
            print(repr("".encode(name)))
        except Exception as exc:
            print(type(exc).__name__, str(exc))


main()
"""

CASES = [('normalized_codec_literals', LITERALS), ('normalized_codec_names', NAMES)]


def build_and_run(directory, text, name, ir):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_IR='1' if ir else '0')
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=600, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=60), expected


class Pre23(unittest.TestCase):
    def check(self, slug, text, ir):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = build_and_run(directory, text, slug + ('_ir' if ir else ''), ir)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def test_cases_default(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug, text, False)

    def test_cases_ir(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug, text, True)


if __name__ == '__main__':
    unittest.main()
