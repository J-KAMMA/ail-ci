"""Branch cov49: str.maketrans / str.translate with dict tables on the general path.

The corpus driver refused `text.translate(TABLE)` (job cov49's fresh profile: 24 refusals,
8 of them stdlib imports; this was the most frequent exactly supportable construct left).
Every program below is compared with CPython 3.12 on both builds: AIL_UNIFIED_FORCE=1 (the
general path) and the default build (which falls back to it). The table shapes that cannot
match stay named compile-time refusals.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}
PROGRAMS['basic'] = r'''import string
TABLE = str.maketrans("aeiou", "AEIOU", ".,!")
print("Hello, world!".translate(TABLE))
print("".translate(TABLE))
print("bcdfg".translate(TABLE))
print("banana".translate(str.maketrans("an", "AN")))
print("banana".translate(str.maketrans("", "", "bn")))
print("abc".translate(str.maketrans("", "")))
print(str.maketrans("ab", "xy"))
print(str.maketrans("", "", "ab"))
print("A-Z".translate(str.maketrans(string.ascii_uppercase, string.ascii_lowercase)))
'''

PROGRAMS['values'] = r'''def apply(text, table):
    return text.translate(table)


class Holder:
    def __init__(self, table):
        self.table = table


holder = Holder(str.maketrans("ab", "AB"))
print(apply("aabb", holder.table))
print("aabb".translate(Holder(str.maketrans("a", "z")).table))
tables = [str.maketrans("abc", "xyz"), str.maketrans("", "", "x")]
print("cab".translate(tables[0]), "axbxc".translate(tables[1]))
by_name = {"punct": str.maketrans("", "", "!?")}
print("Wow!?!".translate(by_name["punct"]))
print("abc".translate({97: 98, 98: None, 99: "ZZ"}))
print("abc".translate({97: 300, 98: -1}))
print("abc".translate({97: "XY"}))
'''

PROGRAMS['errors'] = r'''try:
    str.maketrans("ab", "x")
except ValueError as e:
    print("ValueError", e)
try:
    str.maketrans("a", 1)
except TypeError as e:
    print("TypeError", e)
try:
    str.maketrans("a", "b", 1)
except TypeError as e:
    print("TypeError", e)
try:
    print("abc".translate({97: 1.5}))
except TypeError as e:
    print("TypeError", e)
'''

PROGRAMS['unicode'] = r'''TABLE = str.maketrans("éü", "eu")
print("héllo ünïcode".translate(TABLE))
print("日本".translate(str.maketrans("日", "月")))
'''


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                            source.name, "--syntax", "python", "-o", exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=1800,
                           env=dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env))
    return built, exe


class Programs(unittest.TestCase):
    def check(self, name, **env):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)],
                                  capture_output=True, timeout=300)
            built, exe = build(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0,
                             "%s: %s%s" % (name, built.stdout[-400:], built.stderr[-800:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-400:]))
            self.assertEqual(got.stdout.decode(), want.stdout.decode(), name)

    def test_general_path(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name, AIL_UNIFIED_FORCE="1")

    def test_default_build(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name)


class Refused(unittest.TestCase):
    def refused(self, text, word):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", AIL_UNIFIED_FORCE="1")
            self.assertNotEqual(built.returncode, 0)
            self.assertIn(word, built.stdout + built.stderr)

    def test_one_argument_maketrans(self):
        self.refused("t = str.maketrans({97: 'x'})\nprint('abc'.translate(t))\n",
                     "one argument")

    def test_translate_with_a_list_table(self):
        self.refused("print('abc'.translate([1, 2, 3]))\n", "table literal that is not a dict")


if __name__ == "__main__":
    unittest.main()
