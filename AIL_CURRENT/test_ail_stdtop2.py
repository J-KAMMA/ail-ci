"""unicodedata.category on the general path (stdtop.py + prelude_unicodedata.py), compared with CPython 3.12.

* the prelude (the general category of every code point, as 4000 runs searched by bisection) runs under CPython next
  to unicodedata: all of the Basic Multilingual Plane, every boundary of every run, and a spread of the rest must
  agree, and so must the TypeError texts for a bad argument;
* a Python program is compiled with the default build and with AIL_UNIFIED_FORCE=1 and must print the same bytes as
  CPython (strings in the compiled runtime are 16-bit, so the program stays inside the BMP);
* the rest of unicodedata (name, normalize, numeric, ...) is refused at compile time by name with `write instead:`.
"""
import os
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
for each in (str(PKG), str(ROOT)):
    if each not in sys.path:
        sys.path.insert(0, each)

PROGRAM = r'''
import sys
import unicodedata
from unicodedata import category


def strip_punct(s):
    return "".join(c for c in s if not unicodedata.category(c).startswith("P"))


def classes(s):
    out = {}
    for c in s:
        k = category(c)
        out[k] = out.get(k, 0) + 1
    return sorted(out.items())


def main():
    for line in sys.stdin.read().split("\n"):
        print(repr(line), [category(c) for c in line][:16], strip_punct(line), classes(line))
    for cp in [0, 9, 10, 32, 33, 36, 43, 48, 57, 65, 90, 95, 97, 122, 127, 160, 173, 181, 192, 255, 305, 453, 688, 768, 880, 888, 1632,
               1758, 2404, 3585, 4352, 5760, 8192, 8203, 8232, 8233, 8364, 8482, 8544, 9312, 9728, 10240, 12288, 12354, 12450, 19968,
               40959, 44032, 55203, 57344, 63744, 64256, 65024, 65279, 65281, 65533, 65534, 65535]:
        print(cp, category(chr(cp)))
    for bad in ["", "ab", 5, None, b"a", 1.5, ["x"]]:
        try:
            print(category(bad))
        except Exception as e:
            print(type(e).__name__, e)
    print(unicodedata.unidata_version)


main()
'''

LINES = "\n".join([
    "Hello, World!", "café ¿qué? 中文。 (\"quoted\") -- ok", "áb ² ٠ Ⅰ ­ ​  ",
    "€100 $5 £5 ¥ + = < > | ~ ^ ` ¨", "あア한กअאا", "tab\there", "", " ", "�﻿",
    "͸͹΀"]) + "\n"


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name, "--syntax", "python",
                            "-o", exe.name], cwd=directory, capture_output=True, text=True, timeout=1800,
                           env=dict(os.environ, **env))
    return built, source, exe


class PreludeCategory(unittest.TestCase):
    def test_every_code_point(self):
        import prelude_unicodedata as P
        self.assertEqual(unicodedata.unidata_version, "15.0.0")
        wanted = set(range(0x10000)) | set(range(0x10000, 0x110000, 7)) | {0x10ffff, 0x10fffe, 0xe0001, 0x1f600, 0x20000, 0x2ffff}
        data = P._ail_ud_data
        for i in range(len(data) // 8):
            start = int(data[i * 8:i * 8 + 6], 16)
            wanted.update((start - 1, start, start + 1))
        wanted = sorted(cp for cp in wanted if 0 <= cp < 0x110000)
        for cp in wanted:
            ch = chr(cp)
            want = unicodedata.category(ch)
            got = P._ail_ud_category(ch)
            if got != want:
                self.fail("U+%04X: %s, CPython %s" % (cp, got, want))

    def test_bad_arguments(self):
        import prelude_unicodedata as P
        for bad in ["", "ab", 5, None, b"a", 1.5, ["x"], "\U0001f600\U0001f600"]:
            def call(f):
                try:
                    return ("ok", f(bad))
                except Exception as e:
                    return ("err", type(e).__name__, str(e))
            self.assertEqual(call(P._ail_ud_category), call(unicodedata.category), repr(bad))


class CompiledProgram(unittest.TestCase):
    def test_matches_cpython(self):
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env), tempfile.TemporaryDirectory() as directory:
                built, source, exe = compile_python(directory, PROGRAM, "ud", **env)
                self.assertEqual(built.returncode, 0, "%r\n%s%s" % (env, built.stdout, built.stderr))
                want = subprocess.run([sys.executable, "-X", "utf8", str(source)], input=LINES.encode(), capture_output=True)
                got = subprocess.run([str(exe)], input=LINES.encode(), capture_output=True)
                self.assertEqual(got.returncode, want.returncode, got.stderr[-300:])
                a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                for n, (x, y) in enumerate(zip(a, b)):
                    self.assertEqual(x, y, "line %d %r" % (n + 1, env))
                self.assertEqual(len(a), len(b))


class Refusals(unittest.TestCase):
    CASES = {
        "name": ("import unicodedata\nprint(unicodedata.name('a'))\n", "unicodedata.name is not supported"),
        "normalize": ("import unicodedata\nprint(unicodedata.normalize('NFD', 'e'))\n", "unicodedata.normalize is not supported"),
        "from import": ("from unicodedata import numeric\nprint(numeric('5'))\n", "unicodedata.numeric is not supported"),
        "east_asian_width": ("from unicodedata import east_asian_width as w\nprint(w('a'))\n",
                             "unicodedata.east_asian_width is not supported"),
        "bidirectional": ("import unicodedata as u\nprint(u.bidirectional('a'))\n", "unicodedata.bidirectional is not supported"),
        "module as value": ("import unicodedata\nm = unicodedata\nprint(m.category('a'))\n", "unicodedata used as a value"),
        "star": ("from unicodedata import *\nprint(category('a'))\n", "from unicodedata import *"),
    }

    def test_refusals_name_the_use(self):
        for name, (text, wanted) in self.CASES.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                built, _, exe = compile_python(directory, text, "refused")
                shown = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + name)
                self.assertIn(wanted, shown)
                self.assertIn("write instead:", shown)
                self.assertFalse(exe.exists())
        with tempfile.TemporaryDirectory() as directory:
            built, _, _ = compile_python(directory, self.CASES["name"][0], "refused")
            self.assertRegex(built.stdout + built.stderr, r"refused\.py:2: unicodedata\.name is not supported; write instead: ")


class UnchangedPrograms(unittest.TestCase):
    def test_programs_without_unicodedata_keep_their_text(self):
        import stdlib5
        for text in ["# unicodedata only in a comment\nprint(1)\n", "s = 'import unicodedata'\nprint(s.upper())\n"]:
            notes = []
            self.assertEqual(stdlib5.rewrite_text(text, notes), text)
            self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
