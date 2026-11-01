"""Real programs that use the CPython stdlib module `bisect`, compared with CPython.

The twelve programs in lab/stdlib/bisect/ cover the common calls (bisect_left,
bisect_right, bisect, insort, insort_left, insort_right), the positional and keyword
lo=/hi= bounds (including hi=None), int, float and str lists, empty lists, duplicate
runs, insertion, and the ValueError/IndexError edges the programs catch.  key= on a list
of rows is built by the general path (the typed path does not model a tuple row); its key
function is called on exactly the elements the binary search visits, as CPython does.

Each program is built in the default mode (`--syntax python` without --strict) and its
stdout and exit status are compared byte for byte with CPython's.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "bisect"

PROGRAMS = [
    "grade_report",
    "price_tiers",
    "word_index",
    "leaderboard",
    "event_log",
    "interval_lookup",
    "sparse_ids",
    "alias_import",
    "star_import",
    "key_records",
    "error_edges",
    "lookup_helper",
]

KEY_PROGRAM = r'''import bisect

calls = []


def key(row):
    calls.append(row[0])
    return row[0]


def main():
    rows = [(1, "a"), (2, "b"), (4, "d"), (8, "h")]
    print(bisect.bisect_left(rows, 3, key=key), calls)
    calls.clear()
    print(bisect.bisect_right(rows, 4, key=key), calls)
    calls.clear()
    bisect.insort_left(rows, (3, "c"), key=key)
    print(rows, calls)
    calls.clear()
    bisect.insort_right(rows, (4, "e"), key=key)
    print(rows, calls)
    print(bisect.bisect_left([], 1, key=key), calls)


main()
'''


STR_KEY_PROGRAM = r'''import bisect


class Box:
    def __init__(self):
        self.s = "abcd"


def main():
    print(bisect.bisect_left("abcd", "b", key=str))
    print(bisect.bisect_right("abcd", "c", key=str.lower))
    print(bisect.bisect_left("", "a", key=str))
    box = Box()
    print(bisect.bisect(box.s, "d", key=str))
    table = {"k": "abcd"}
    print(bisect.bisect_left(table["k"], "a", key=str))
    t = ("a", "b", "d")
    print(bisect.bisect_left(t, "c", key=str))
    print(bisect.bisect_right(t, "b", key=str))
    try:
        bisect.bisect_left("abc", "b", 0, 10, key=str)
    except IndexError as e:
        print(type(e).__name__, e)
    try:
        bisect.insort("abc", "b", key=str)
    except AttributeError as e:
        print(type(e).__name__, e)
    try:
        bisect.insort_left(t, "c", key=str)
    except AttributeError as e:
        print(type(e).__name__, e)


main()
'''


def build_and_run(directory, source):
    local = Path(directory) / source.name
    shutil.copyfile(source, local)
    exe = Path(directory) / "prog"
    env = dict(os.environ, AIL_NO_CACHE="1")
    built = subprocess.run(
        [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", local.name,
         "--syntax", "python", "-o", exe.name],
        cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return built, local, exe


@unittest.skipUnless(LAB.is_dir(), "lab/stdlib/bisect is not part of this tree")
class StdlibBisect(unittest.TestCase):
    def check(self, source, label):
        with tempfile.TemporaryDirectory() as directory:
            built, local, exe = build_and_run(directory, source)
            self.assertEqual(built.returncode, 0, "%s\n%s%s" % (label, built.stdout[-2000:], built.stderr[-3000:]))
            want = subprocess.run([sys.executable, "-X", "utf8", str(local)],
                                  capture_output=True, timeout=120)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual(got.returncode, want.returncode,
                             "%s: exit %d against CPython's %d\n%s"
                             % (label, got.returncode, want.returncode, got.stderr.decode("utf-8", "replace")[-1000:]))
            self.assertEqual(got.stdout, want.stdout,
                             "%s:\n compiled: %r\n CPython:  %r"
                             % (label, got.stdout.decode("utf-8", "replace"),
                                want.stdout.decode("utf-8", "replace")))

    def test_lab_programs_match_cpython(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                source = LAB / (name + ".py")
                self.assertTrue(source.is_file(), source)
                self.check(source, name)

    def test_key_calls_and_insort(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "key_calls.py"
            source.write_text(KEY_PROGRAM, encoding="utf-8")
            self.check(source, "key_calls")

    def test_key_on_str_and_tuple(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "str_key.py"
            source.write_text(STR_KEY_PROGRAM, encoding="utf-8")
            self.check(source, "str_key")


if __name__ == "__main__":
    unittest.main()
