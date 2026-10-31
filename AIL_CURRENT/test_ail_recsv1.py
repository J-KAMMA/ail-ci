"""recsv1: a typed `csv` reader must not silently return str cells for QUOTE_NONNUMERIC.

CPython's reader converts every unquoted field to float under QUOTE_NONNUMERIC (quoted fields stay
str, an empty unquoted field stays ''). csvlib's list-and-cursor lowering can only hold str cells, so
it refuses the constructor by name and the general path (prelude_csv.py, whose reader calls
float()) builds the program. Every project below is ordinary Python: CPython is the oracle and both
builds must print the same bytes; with the general path unavailable the constructor is refused by
name -- there is no third outcome where the cells differ.

The source list reaches the constructor as a literal and through an argument, a list item, an
attribute and a dict value; rows are reached by list(), next(), a for loop, enumerate() and
DictReader.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}
PROGRAMS['literal'] = r'''import csv


def tag(v):
    if isinstance(v, float):
        return "f"
    if isinstance(v, str):
        return "s"
    return "?"


def dump(rows):
    for row in rows:
        line = []
        for v in row:
            line.append(tag(v) + ":" + repr(v))
        print(line)


dump(list(csv.reader(['1,2.5,"a",3', '-2,-0.5,"-4",1e3', 'nan,inf,"5",""', '3,,"4",5'],
                     quoting=csv.QUOTE_NONNUMERIC)))
print(list(csv.reader(['1,2.5,"a",3'], quoting=csv.QUOTE_NONNUMERIC)))
print(list(csv.reader(['12345678901234567890,-12345678901234567890.5'], quoting=csv.QUOTE_NONNUMERIC)))
'''
PROGRAMS['routes'] = r'''import csv


class Holder:
    def __init__(self, lines):
        self.lines = lines


def tag(v):
    if isinstance(v, float):
        return "f"
    if isinstance(v, str):
        return "s"
    return "?"


def dump(label, rows):
    print(label, [tag(v) for v in rows[0]], rows)


def from_arg(lines):
    return list(csv.reader(lines, quoting=csv.QUOTE_NONNUMERIC))


dump("arg", from_arg(['1,2.5,"x"']))
grid = [['7,8.5'], ['9,10']]
dump("item", list(csv.reader(grid[0], quoting=csv.QUOTE_NONNUMERIC)))
h = Holder(['1.5,-2'])
dump("attr", list(csv.reader(h.lines, quoting=csv.QUOTE_NONNUMERIC)))
d = {'lines': ['3,4.25']}
dump("dict", list(csv.reader(d['lines'], quoting=csv.QUOTE_NONNUMERIC)))
lines = ['1,2', '3.5,"4"']
r1 = list(csv.reader(lines, quoting=csv.QUOTE_NONNUMERIC))
r2 = list(csv.reader(lines, quoting=csv.QUOTE_NONNUMERIC))
print("alias", lines, r1, r2)
'''
PROGRAMS['edges'] = r'''import csv


def tryshow(lines):
    try:
        rows = list(csv.reader(lines, quoting=csv.QUOTE_NONNUMERIC))
        print(rows)
    except ValueError as e:
        print("VE", e)


tryshow(['1,b'])
tryshow(['1,,2'])
tryshow(['"a",2'])
tryshow(['"1",2'])
tryshow(['1e400,-1e400'])
tryshow(['  1, 2'])
tryshow([''])
tryshow([])

for row in csv.reader(['1,2.5'], quoting=csv.QUOTE_NONNUMERIC):
    print(row)
r = csv.reader(['1,2.5'], quoting=csv.QUOTE_NONNUMERIC)
print(next(r))
print(list(r))
print(list(enumerate(csv.reader(['7,8.5'], quoting=csv.QUOTE_NONNUMERIC))))
print(list(csv.DictReader(['1,2', '3,4.5', '5.5,"6"'], quoting=csv.QUOTE_NONNUMERIC)))
try:
    print(list(csv.DictReader(['a,b', '1,2'], quoting=csv.QUOTE_NONNUMERIC)))
except ValueError as e:
    print("VE", e)
'''
PROGRAMS['defaults'] = r'''import csv

print(list(csv.reader(['1,2.5,"a",3'])))
r = csv.reader(['x,y', 'z,w'])
print(next(r), list(r))
for row in csv.reader(['4,5']):
    print(row)
print(list(csv.DictReader(['a,b', '1,2'])))
print(list(csv.reader(['a,b', 'c,d'], quoting=csv.QUOTE_ALL)))
print(list(csv.reader(['a,,b'], quoting=csv.QUOTE_NONE, escapechar='\\')))
'''


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800,
                           env=dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env))
    return built, exe


class Programs(unittest.TestCase):
    def check(self, name, **env):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True,
                                  timeout=300)
            built, exe = build(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s: %s%s" % (name, built.stdout[-400:],
                                                                built.stderr[-600:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-300:]))
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
            built, _ = build(directory, text, "r", AIL_NO_GENERAL="1")
            self.assertNotEqual(built.returncode, 0)
            self.assertIn(word, built.stdout + built.stderr)

    def test_reader_refused_by_name(self):
        self.refused("import csv\n\nlines = ['1,2.5']\n"
                     "print(list(csv.reader(lines, quoting=csv.QUOTE_NONNUMERIC)))\n",
                     "csv.QUOTE_NONNUMERIC is not built for a reader")

    def test_dictreader_refused_by_name(self):
        self.refused("import csv\n\nlines = ['1,2', '3,4']\n"
                     "print(list(csv.DictReader(lines, quoting=csv.QUOTE_NONNUMERIC)))\n",
                     "csv.QUOTE_NONNUMERIC is not built for a reader")

    def test_writer_refused_by_name(self):
        self.refused("import csv\nimport sys\n\n"
                     "w = csv.writer(sys.stdout, quoting=csv.QUOTE_NONNUMERIC)\nw.writerow([1])\n",
                     "QUOTE_NONNUMERIC")


if __name__ == "__main__":
    unittest.main()
