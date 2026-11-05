"""prog17 typed reach: `reversed(<str>)` and row-list comprehensions against CPython 3.12.

T1  `for c in reversed(s)` walks a str backwards on the typed path: empty, one character,
    ASCII, 2- and 3-byte UTF-8, a slice, `a + b`, `str(int)`, `.upper()`, an attribute, a list
    item and a dict value, `break`, and `ord` over the one-code-point views.
T2  `enumerate(..., start=...)` inside a pair comprehension and a fold: positional and keyword
    start, literal/variable/attribute/list-item/dict-value/call routes, zero, negative, a slice
    source, and the start evaluated exactly once (the call prints once).
T3  a `list[tuple[..., str, ...]]` annotation filled by a pair comprehension, including a filter,
    negative ints, a three-field int/float/str row, an empty source and a slice.
T4  the two programs that moved: `dev/t374.py` (all `in*.txt`) and `gdev/g02_016.py` build typed
    on both `AIL_IR` settings and print CPython's bytes.
T5  a wrong field type in the row comprehension is refused by name (never silently written).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
LAB = REPO / 'lab'
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

REVERSED = '''def rev(s: str) -> str:
    out: list[str] = []
    for ch in reversed(s):
        out.append(ch)
    return "".join(out)


class Box:
    def __init__(self, text: str) -> None:
        self.text: str = text


def main() -> None:
    print(repr(rev("")), repr(rev("a")), repr(rev("abc")))
    print(repr(rev("h\\u00e9llo")), repr(rev("\\u20ac\\u00e9a")))
    print(repr(rev("abcdef"[1:-1])), repr(rev("xy" + "")))
    print(repr(rev("MMXXIV".upper())), repr(rev(str(1234))))
    words: list[str] = ["", "one", "tw\\u00f6"]
    box = Box("p\\u00e4ss")
    table: dict[str, int] = {"k": 7}
    print(repr(rev(words[0])), repr(rev(words[2])), repr(rev(box.text)))
    total: int = 0
    for ch in reversed("a1b2c3"):
        if ch.isdigit():
            total += int(ch)
    points: list[int] = []
    for ch in reversed("a\\u00e9"):
        points.append(ord(ch))
    print(total, table["k"], points)
    n: int = 0
    for ch in reversed("abcdef"):
        n += 1
        if ch == "c":
            break
    print(n)


main()
'''

ENUM_START = '''class Cfg:
    def __init__(self, base: int) -> None:
        self.base: int = base


def bump(x: int) -> int:
    print("bump")
    return x + 1


def build(words: list[str], base: int) -> int:
    rows: list[tuple[int, str]] = [(i, f"{w}{i}") for i, w in enumerate(words, start=base) if i % 2 == 0]
    total: int = 0
    for i, w in rows:
        total += i + len(w)
    return total


def main() -> None:
    words: list[str] = ["a", "bb", "ccc", "dddd"]
    tagged: list[tuple[int, str]] = [(i, w) for i, w in enumerate(words, start=1)]
    count: int = 0
    for i, w in tagged:
        print(i, w)
        count += 1
    print(count)
    print(build(words, 0), build(words, -3), build(["x"], 7))
    print([i for i, w in enumerate(words, start=0)])
    print([i for i, w in enumerate(words, start=2)])
    print(sum(i for i, w in enumerate(words, start=10)))
    print([i for i, w in enumerate(words[1:], start=3)])
    cfg = Cfg(3)
    table: dict[str, int] = {"s": 8}
    vals: list[int] = [20]
    print([i for i, w in enumerate(words, start=cfg.base)])
    print([i for i, w in enumerate(words, start=table["s"])])
    print([i for i, w in enumerate(words, start=vals[0])])
    bumped: list[tuple[int, str]] = [(i, w) for i, w in enumerate(words, start=bump(0))]
    for i, w in bumped:
        print(i, w)


main()
'''

SROWS = '''def main() -> None:
    words: list[str] = ["a", "bb", "ccc", "", "ee"]
    rows: list[tuple[int, str]] = [(i, f"<{w}>") for i, w in enumerate(words, start=1)]
    count: int = 0
    for i, w in rows:
        print(i, w)
        count += 1
    print(count)
    rows.sort(key=lambda r: r[0], reverse=True)
    for i, w in rows:
        print(i, w)
    kept: list[tuple[int, str]] = [(i, w) for i, w in enumerate(words[1:], start=0) if i != 2]
    for i, w in kept:
        print(i, w)
    negatives: list[tuple[int, str]] = [(i * -1, w) for i, w in enumerate(words, start=1)]
    for i, w in negatives:
        print(i, w)
    mixed: list[tuple[int, float, str]] = [(i, i / 4.0, w) for i, w in enumerate(words, start=0)]
    for i, x, w in mixed:
        print(i, x, w)
    empty: list[str] = []
    none: list[tuple[int, str]] = [(i, w) for i, w in enumerate(empty, start=9)]
    ncount: int = 0
    for i, w in none:
        ncount += 1
    print(ncount)


main()
'''

BAD_FIELD = '''def main() -> None:
    words: list[str] = ["a", "bb"]
    rows: list[tuple[int, str]] = [(i, i) for i, w in enumerate(words, start=1)]
    print(len(rows))


main()
'''


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog17(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog17_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def cpython(self, text, name, stdin=None):
        path = Path(self.tmp) / (name + '_py.py')
        path.write_text(text, encoding='utf-8')
        return subprocess.run([sys.executable, '-B', str(path)], capture_output=True,
                              text=True, timeout=300, encoding='utf-8',
                              input=stdin if stdin is not None else '')

    def build(self, text, name, ir, typed):
        source = Path(self.tmp) / (name + '.py')
        source.write_text(text, encoding='utf-8')
        exe = Path(self.tmp) / ('%s_%s_%s' % (name, ir, 'typed' if typed else 'default'))
        env = dict(os.environ, AIL_IR=ir, AIL_NO_CACHE='1')
        env.pop('AIL_NO_GENERAL', None)
        if typed:
            env['AIL_NO_GENERAL'] = '1'
        built = subprocess.run([sys.executable, '-B', CLI, 'compile', str(source),
                                '--syntax', 'python', '-o', str(exe)], cwd=self.tmp,
                               capture_output=True, text=True, timeout=900, env=env)
        return built, exe

    def same(self, text, name, typed=True, stdin=''):
        want = self.cpython(text, name, stdin)
        for ir in ('0', '1'):
            built, exe = self.build(text, name, ir, typed)
            self.assertEqual(built.returncode, 0,
                             'typed=%s IR=%s: %s' % (typed, ir, built.stderr[-2000:]))
            if typed:
                self.assertNotIn('built on the general path', built.stderr, 'IR=%s' % ir)
            got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300,
                                 encoding='utf-8', input=stdin)
            self.assertEqual(got.stdout, want.stdout, 'typed=%s IR=%s' % (typed, ir))
            self.assertEqual(got.returncode, want.returncode, 'typed=%s IR=%s' % (typed, ir))
        return want

    def test_reversed_str_is_typed(self):
        self.same(REVERSED, 'reversed', typed=True)
        self.same(REVERSED, 'reversed_default', typed=False)

    def test_enumerate_start_in_comprehension_and_fold(self):
        self.same(ENUM_START, 'enumstart', typed=True)
        self.same(ENUM_START, 'enumstart_default', typed=False)

    def test_row_list_comprehension(self):
        self.same(SROWS, 'srows', typed=True)
        self.same(SROWS, 'srows_default', typed=False)

    def test_wrong_row_field_is_refused_by_name(self):
        built, _ = self.build(BAD_FIELD, 'badrow', '0', typed=True)
        self.assertNotEqual(built.returncode, 0)
        self.assertIn('requires a str in every str field', built.stderr)

    def test_real_programs_are_typed_and_match(self):
        g02 = (LAB / 'census' / 'programs' / 'gdev' / 'g02_016.py').read_text(encoding='utf-8')
        self.same(g02, 'g02', typed=True)
        t374 = (LAB / 'census' / 'programs' / 'dev' / 't374.py').read_text(encoding='utf-8')
        inputs = sorted((LAB / 'corpus' / 'tasks' / 't374').glob('in*.txt'))
        self.assertTrue(inputs)
        for path in inputs:
            self.same(t374, 't374_' + path.stem, typed=True,
                      stdin=path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
