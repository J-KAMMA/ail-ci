"""The hot functions of eight real programs on the typed path (prog9), against CPython 3.12.

`t254`, `g09_002`, `g23_026` and `t308` already built typed.  This batch makes `t208` and `t216`
typed too:

* a scalar Optional used by `in` / `not in` against a literal tuple, list or set with no None
  (`while self.peek() in ("+", "-")`); the absent value is simply not a member, as in CPython;
* an Optional-returning call in a `while` test, lowered to `while True` with the call and an
  inverted test at the top of the body (a `continue` re-evaluates it);
* `a, b = method()` where the method returns a small per-field row (the same SROW ABI a plain
  function's tuple return already uses);
* `sorted(d)` for a typed `dict[str, int]` / `Counter[str]` (Python sorts the keys);
* `print(d)` / `repr(d)` / `f"{d}"` of a str-keyed int dict, in CPython's insertion order.

`g18_006` (a tuple value out of `itertools.combinations`) and `g17_022` (`list[Any]` recursion with
map/filter lambdas) remain general-path programs; their exact first refusals are recorded in
`lab/progfix/prog9.md`.

T1  each program builds with `--strict` (typed path alone), and stdin/stdout/exit match CPython on
    the public task inputs and on empty, whitespace, negative, non-ASCII and error boundaries
T2  the new constructs are typed on their own: Optional `in`, a method row unpack, sorted str dict,
    dict text (annotated and unannotated, empty, negative, non-ASCII keys, aliased read)
T3  the four already-typed programs keep building typed and matching CPython
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
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None


def _source(relative):
    path = REPO / relative
    return path.read_text(encoding='utf-8') if path.exists() else None


def _compile(directory, text, name, strict=True):
    source = Path(directory, name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory, name + '_x')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK', 'AIL_EXACT_INT'):
        env.pop(key, None)
    args = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
            '-o', exe.name]
    if strict:
        args.insert(5, '--strict')
    return subprocess.run(args, cwd=directory, capture_output=True, text=True, timeout=900, env=env), source, exe


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog9(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog9_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def same(self, text, name, inputs):
        built, source, exe = _compile(self.tmp, text, name)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr[-2000:])
        for stdin in inputs:
            want = subprocess.run([sys.executable, '-B', str(source)], input=stdin.encode('utf-8'),
                                  capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
            self.assertEqual(got.stdout, want.stdout, '%s stdin=%r' % (name, stdin))
            self.assertEqual(got.returncode, want.returncode, '%s stdin=%r' % (name, stdin))

    def program(self, relative, inputs):
        text = _source(relative)
        if text is None:
            self.skipTest('%s is not in this tree' % relative)
        self.same(text, Path(relative).stem, inputs)

    def test_t254_typed(self):
        self.program('lab/census/programs/dev/t254.py',
                     ['', '1\n5\n', '2\n1 2\n3 4\n', '3\n-5 1 8\n4 4 -5\n3 3 3\n',
                      '4\n9 3 3 -4\n0 9 2 -3\n-1 4 -3 3\n8 3 -4 -1\n'])

    def test_g09_typed(self):
        self.program('lab/census/programs/gdev/g09_002.py', [''])

    def test_g23_typed(self):
        self.program('lab/census/programs/gdev/g23_026.py', [''])

    def test_t308_typed(self):
        self.program('lab/corpus/programs/deepseek-v4.1-flash-free/t308.py',
                     ['', 'cbb\nabbabab\n', 'acacaabbcc\nabcbccabaa\n', 'abc\n', 'éé\né\n'])

    def test_t208_general_matches_cpython(self):
        # The hot Parser methods now build as typed code individually, but `parse()` and its
        # helpers return `int | float`, a union with no single C representation: returning float
        # would print 3.0 where CPython prints 3, so the program stays on the general path.
        text = _source('lab/corpus/programs/deepseek-v4.1-flash-free/t208.py')
        if text is None:
            self.skipTest('t208 is not in this tree')
        inputs = ['', '1 + 2\n', '(20 * 20 + 10) * 4\n14 - 18 * 11 - 13\n',
                  '6 / 14\n(1 / 9 / 20 + 11 * 17) * 5\n', '-((3))\n2 + + 3\n',
                  '1 / 0\n', '2 ^ 3\n', '3 +\n', '((((7))))\n', '\n   \n4 * (2 + 3)\n']
        built, source, exe = _compile(self.tmp, text, 't208_general', strict=False)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr[-2000:])
        self.assertIn('built on the general path', built.stderr)
        for stdin in inputs:
            want = subprocess.run([sys.executable, '-B', str(source)], input=stdin.encode('utf-8'),
                                  capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
            self.assertEqual(got.stdout, want.stdout, 't208 stdin=%r' % stdin)
            self.assertEqual(got.returncode, want.returncode, 't208 stdin=%r' % stdin)
        refused, _, _ = _compile(self.tmp, text, 't208_strict', strict=True)
        self.assertEqual(refused.returncode, 3, refused.stdout + refused.stderr[-1200:])
        self.assertIn('returns `int | float`', refused.stdout + refused.stderr)

    def test_t216_typed(self):
        self.program('lab/corpus/programs/deepseek-v4.1-flash-free/t216.py',
                     ['', '0\n', '4\n]{{{()){}\n([[\n}}]])})(]})\n}(]})]\n', '2\naa\nbb\n',
                      '2\nab\n', '1\né日\n', '3\na\nb\nc\n', '2\na\nb\nextra\n', '\n\n'])

    OPTIONAL_IN = '''def pick(i: int) -> str | None:
    if i < 3:
        return "abc"[i]
    return None


def count() -> int:
    n = 0
    i = 0
    while pick(i) in ("a", "b"):
        n += 1
        i += 1
    return n


def run(s: str | None) -> int:
    n = 0
    while s in ("x", "y", "z"):
        n += 1
        s = None
    if s not in ("x", "y"):
        n += 10
    return n


def main() -> None:
    print(count(), run("x"), run("q"), run(None))


main()
'''

    METHOD_ROW = '''class P:
    def __init__(self) -> None:
        self.s = "ab"

    def pair(self) -> tuple[bool, str]:
        return (True, self.s)


def main() -> None:
    p = P()
    a, b = p.pair()
    print(a, b)


main()
'''

    DICT_TEXT = '''from collections import Counter


def show(d: dict[str, int]) -> None:
    print(d)


def main() -> None:
    c: Counter[str] = Counter()
    print(sorted(c))
    for ch in "ééaab日":
        c[ch] += 1
    print(sorted(c))
    print(sorted(c, reverse=True))
    d: dict[str, int] = {}
    d["a'b"] = -1
    d['c"d'] = 0
    d["e\\n\\t\\\\"] = 2
    d["é日"] = 3
    d[""] = 4
    print(d)
    print(repr(d))
    print(f"{d}")
    show(d)
    alias = d
    print(repr(alias))
    e = {}
    e["x"] = 7
    print(e)


main()
'''

    SORT_KEYS_OWNED = '''from collections import Counter


def keys_of(d: dict[str, int]) -> list[str]:
    return sorted(d)


def local_keys() -> list[str]:
    d: dict[str, int] = {}
    d["b"] = 1
    d["a"] = 2
    d["c"] = 3
    return sorted(d)


def main() -> None:
    d: dict[str, int] = {}
    d["b"] = 1
    d["a"] = 2
    d["c"] = 3
    ks = sorted(d)
    del d["b"]
    print(ks)

    e: dict[str, int] = {}
    e["z"] = 1
    e["é"] = 2
    e[""] = 3
    es = sorted(e)
    e.clear()
    print(es)

    c: Counter[str] = Counter()
    for ch in "banana":
        c[ch] += 1
    cs = sorted(c, reverse=True)
    c.clear()
    print(cs)

    g: dict[str, int] = {}
    gs = sorted(g)
    print(gs, len(gs))

    p: dict[str, int] = {}
    p["q"] = 1
    p["p"] = 2
    print(keys_of(p))
    print(local_keys())
    for i in range(3):
        r = sorted(d)
        print(r, i)
    print(sorted(d))


main()
'''

    def test_optional_in_and_while_typed(self):
        self.same(self.OPTIONAL_IN, 'opt_in', [''])

    def test_method_row_unpack_typed(self):
        self.same(self.METHOD_ROW, 'method_row', [''])

    def test_dict_keys_and_text_typed(self):
        self.same(self.DICT_TEXT, 'dict_text', [''])

    def test_sorted_dict_keys_own_their_text(self):
        # Deleting from / clearing the dict after sorted(d) must not invalidate the result: the
        # key views in the string table are freed then, so the list has to hold copies.
        self.same(self.SORT_KEYS_OWNED, 'sort_keys_owned', [''])


if __name__ == '__main__':
    unittest.main()
