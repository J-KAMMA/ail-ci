"""Python-syntax reach, s2: stepped slices, `del`, `reversed()`, heapq on a subscript, nsmallest.

S1  `xs[a:b:k]` of a list, str or bytes with a literal, nonzero step -- either sign, `[::-1]`
    included -- copies CPython's `slice.indices` clamping: negative indices, defaults per sign,
    an empty range, and bounds far past the end (also one read from stdin).
S2  A literal or computed step of 0 raises the ValueError CPython raises.
S3  `del name` of a local that is never read again is dropped; a later read keeps CPython's
    UnboundLocalError.
S4  `reversed(x)` walks a list, str or bytes backwards in a `for`, `xs.extend(reversed(x))`
    and `list(reversed(x))`; a str is walked one code point per step.
S5  `heappush(free[c], v)` / `heappop(alias)` change the inner list in place: another name over
    the same list sees the change, as in CPython.
S6  `heapq.nsmallest(k, xs)` / `nlargest(k, xs)` equal `sorted(xs)[:k]` / `sorted(xs,
    reverse=True)[:k]` for ints and lists of str, including ties, k <= 0 and k past the end.
S7  `lab/compare/src/berth_sim/main.py` builds on the typed path with no blocker.
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
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None


SLICE_INT = '''def main():
    xs = [10, 20, 30, 40, 50, 60, 70]
    print(xs[1:10:3])
    print(xs[::-1])
    print(xs[-1:-10:-2])
    print(xs[5:1:2])
    print(xs[-100:100:7])
    print(xs[::2])
    print(xs[6:0:-3])
    print(xs[2:2:3])
    print(xs[-2::-1])
    print(xs[:100:-1])
    print(len(xs[1:3:2]))
    total = 0
    for v in xs[::-2]:
        total += v
    print(total)
    ys = []
    ys.extend(xs[1:10:3])
    print(ys)
    data = "1234567"
    print(list(map(int, data[1:6:2])))
    big = 4611686018427387904
    print(xs[big:big + 3:1])
    print(xs[:big:2])
    print(xs[big::-2])
    print(xs[-big:big:3])


main()
'''

SLICE_STR = '''def main():
    s = "abcdef"
    print(s[1:10:3])
    print(s[::-1])
    print("h\\u00e9llo"[::-1])
    print(s[-100:100:7])
    print(s[4:0:-2])
    for c in s[::-1]:
        print(c)
    print(len(s[::2]))


main()
'''

SLICE_BYTES = '''def main():
    b = b"abcdef"
    print(b[::2] == b"ace")
    print(b[::-1] == b"fedcba")
    print(len(b[1:10:3]))
    for v in b[::2]:
        print(v)
    for v in b[::-1]:
        print(v)
    print(list(b[::2]))


main()
'''

SLICE_STDIN = '''def main():
    a = int(input())
    xs = [10, 20, 30, 40, 50, 60, 70]
    print(xs[a:a + 100:3])
    print(xs[a::-2])
    print(xs[:a:2])


main()
'''

SLICE_ZERO = '''def main():
    xs = [1, 2, 3]
    i = 0
    print(xs[0:2:i])


main()
'''

SLICE_ZERO_LITERAL = '''def main():
    xs = [1, 2, 3]
    print(xs[0:2:0])


main()
'''

DEL_DROP = '''def main():
    data = "abc"
    keys = [1, 2]
    order = 3
    print(len(data), keys[0], order)
    del data
    del keys
    del order
    print("done")


main()
'''

DEL_READ = '''def f(n):
    x = n * 2
    print(x)
    del x
    return n + 1

def g(n):
    y = n * 3
    del y
    print(y)

def main():
    print(f(4))
    g(2)


main()
'''

REVERSED = '''def main():
    xs = [1, 2, 3]
    for v in reversed(xs):
        print(v)
    s = "h\\u00e9llo"
    for c in reversed(s):
        print(c)
    b = b"xyz"
    for v in reversed(b):
        print(v)
    empty = []
    for v in reversed(empty):
        print(v)
    out = []
    out.extend(reversed(xs))
    print(out)
    print(list(reversed(xs)))
    print(list(reversed(s)))
    print(list(reversed(b)))
    words: list[str] = []
    words.extend(reversed(s))
    print(words)


main()
'''

HEAP_SUBSCRIPT = '''from heapq import heappush, heappop

def main():
    free = [[], [], []]
    cls = [0, 1, 2]
    b = 2
    heappush(free[cls[b]], b)
    heappush(free[0], 5)
    heappush(free[0], 1)
    print(free[0], free[1], free[2])
    bw = free[0]
    heappush(bw, 3)
    print(free[0])
    print(heappop(bw))
    print(free[0])
    print(sum(free[0]))


main()
'''

NSMALLEST = '''import heapq

def main():
    xs = [3, 1, 3, 1, 2]
    print(heapq.nsmallest(3, xs))
    print(heapq.nsmallest(5, xs))
    print(heapq.nsmallest(9, xs))
    print(heapq.nsmallest(0, xs))
    print(heapq.nsmallest(-4, xs))
    print(heapq.nlargest(2, xs))
    print(heapq.nlargest(0, xs))
    print(heapq.nlargest(9, xs))
    words = ["pear", "apple", "fig", "apple"]
    print(heapq.nsmallest(2, words))
    print(heapq.nlargest(3, words))
    empty = []
    print(heapq.nsmallest(2, empty))
    print(heapq.nlargest(2, empty))
    top = heapq.nsmallest(2, xs)
    print(top)
    print(len(top))
    top[0] = 100
    print(top, xs)
    for v in heapq.nlargest(3, xs):
        print(v)
    k = 2
    print(heapq.nsmallest(k, xs))
    print(heapq.nlargest(k + 1, xs))
    print(heapq.nsmallest(len(xs) - 1, xs))


main()
'''

NSMALLEST_TUPLES = '''import heapq

def main():
    pairs = [(2, 1), (1, 5), (3, 0)]
    print(heapq.nsmallest(2, pairs))


main()
'''


def build_source(tmp, name, source):
    exe = Path(tmp) / name
    env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '--strict', '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def build_probe(tmp, name, source, unified):
    exe = Path(tmp) / (name + ('_unified' if unified else '_default'))
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    env.pop('AIL_NO_GENERAL', None)
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def run(exe, stdin=None):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                          input=stdin)


def cpython(source):
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True,
                          timeout=120)


def cpython_stdin(source, data):
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True,
                          timeout=120, input=data)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class PyreachShapes(unittest.TestCase):
    def _typed(self, name, text, expected, stdin=None):
        """The strict (typed-only) build succeeds and matches `expected`."""
        with tempfile.TemporaryDirectory(prefix='ail-s2-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            result, exe = build_source(tmp, name, source)
            self.assertEqual(result.returncode, 0, (name, result.stderr[-3000:]))
            got = run(exe, stdin)
            self.assertEqual(got.stdout, expected, (name, got.stderr[-2000:]))

    def _both(self, name, text, expected, stdin=None):
        """Both builds (default and AIL_UNIFIED_FORCE=1) match `expected`."""
        with tempfile.TemporaryDirectory(prefix='ail-s2-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            for unified in (False, True):
                result, exe = build_probe(tmp, name, source, unified)
                self.assertEqual(result.returncode, 0,
                                 (name, unified, result.stderr[-3000:]))
                got = run(exe, stdin)
                self.assertEqual(got.stdout, expected, (name, unified, got.stderr[-2000:]))

    def test_stepped_slice_int(self):
        expected = ('[20, 50]\n[70, 60, 50, 40, 30, 20, 10]\n[70, 50, 30, 10]\n[]\n[10]\n'
                    '[10, 30, 50, 70]\n[70, 40]\n[]\n[60, 50, 40, 30, 20, 10]\n[]\n1\n160\n'
                    '[20, 50]\n[2, 4, 6]\n[]\n[10, 30, 50, 70]\n[70, 50, 30, 10]\n'
                    '[10, 40, 70]\n')
        self._typed('slice_int', SLICE_INT, expected)
        self._both('slice_int', SLICE_INT, expected)

    def test_stepped_slice_str(self):
        expected = 'be\nfedcba\noll\u00e9h\na\nec\nf\ne\nd\nc\nb\na\n3\n'
        self._typed('slice_str', SLICE_STR, expected)
        self._both('slice_str', SLICE_STR, expected)

    def test_stepped_slice_bytes(self):
        expected = 'True\nTrue\n2\n97\n99\n101\n102\n101\n100\n99\n98\n97\n[97, 99, 101]\n'
        self._typed('slice_bytes', SLICE_BYTES, expected)
        self._both('slice_bytes', SLICE_BYTES, expected)

    def test_stepped_slice_bound_from_input(self):
        with tempfile.TemporaryDirectory(prefix='ail-s2-') as tmp:
            source = Path(tmp) / 'slice_stdin.py'
            source.write_text(SLICE_STDIN, encoding='utf8')
            for index, data in enumerate(('3\n', '100\n', '4611686018427387904\n',
                                          '-4611686018427387904\n')):
                name = 'slice_stdin%d' % index
                reference = cpython_stdin(source, data)
                self.assertEqual(reference.returncode, 0, data)
                result, exe = build_source(tmp, name, source)
                self.assertEqual(result.returncode, 0, (data, result.stderr[-3000:]))
                got = run(exe, data)
                self.assertEqual(got.stdout, reference.stdout, data)
                for unified in (False, True):
                    result, exe = build_probe(tmp, name, source, unified)
                    self.assertEqual(result.returncode, 0,
                                     (data, unified, result.stderr[-3000:]))
                    got = run(exe, data)
                    self.assertEqual(got.stdout, reference.stdout, (data, unified))

    def test_zero_step_raises_value_error(self):
        for name, text in (('slice_zero_var', SLICE_ZERO),
                           ('slice_zero_lit', SLICE_ZERO_LITERAL)):
            with tempfile.TemporaryDirectory(prefix='ail-s2-') as tmp:
                source = Path(tmp) / (name + '.py')
                source.write_text(text, encoding='utf8')
                reference = cpython(source)
                self.assertEqual(reference.returncode, 1, name)
                for unified in (False, True):
                    result, exe = build_probe(tmp, name, source, unified)
                    self.assertEqual(result.returncode, 0,
                                     (name, unified, result.stderr[-3000:]))
                    got = run(exe)
                    self.assertEqual(got.returncode, 1, (name, unified))
                    self.assertEqual(got.stdout, reference.stdout, (name, unified))
                    self.assertIn('slice step cannot be zero', got.stderr, (name, unified))

    def test_del_name_without_later_read(self):
        self._typed('del_drop', DEL_DROP, '3 1 3\ndone\n')
        self._both('del_drop', DEL_DROP, '3 1 3\ndone\n')

    def test_del_then_read_keeps_unbound_local_error(self):
        with tempfile.TemporaryDirectory(prefix='ail-s2-') as tmp:
            source = Path(tmp) / 'del_read.py'
            source.write_text(DEL_READ, encoding='utf8')
            reference = cpython(source)
            self.assertEqual(reference.returncode, 1)
            for unified in (False, True):
                result, exe = build_probe(tmp, 'del_read', source, unified)
                self.assertEqual(result.returncode, 0, (unified, result.stderr[-3000:]))
                got = run(exe)
                self.assertEqual(got.returncode, 1, unified)
                self.assertEqual(got.stdout, reference.stdout, unified)
                self.assertIn('UnboundLocalError', got.stderr, unified)

    def test_reversed_list_str_bytes(self):
        expected = ('3\n2\n1\no\nl\nl\n\u00e9\nh\n122\n121\n120\n[3, 2, 1]\n[3, 2, 1]\n'
                    "['o', 'l', 'l', '\u00e9', 'h']\n[122, 121, 120]\n"
                    "['o', 'l', 'l', '\u00e9', 'h']\n")
        self._typed('reversed_shapes', REVERSED, expected)
        self._both('reversed_shapes', REVERSED, expected)

    def test_heap_on_subscript_and_alias_shares_the_list(self):
        expected = '[1, 5] [] [2]\n[1, 5, 3]\n1\n[3, 5]\n8\n'
        self._typed('heap_subscript', HEAP_SUBSCRIPT, expected)
        self._both('heap_subscript', HEAP_SUBSCRIPT, expected)

    def test_nsmallest_nlargest(self):
        expected = ('[1, 1, 2]\n[1, 1, 2, 3, 3]\n[1, 1, 2, 3, 3]\n[]\n[]\n[3, 3]\n[]\n'
                    '[3, 3, 2, 1, 1]\n'
                    "['apple', 'apple']\n['pear', 'fig', 'apple']\n[]\n[]\n"
                    '[1, 1]\n2\n[100, 1] [3, 1, 3, 1, 2]\n3\n3\n2\n[1, 1]\n[3, 3, 2]\n'
                    '[1, 1, 2, 3]\n')
        self._typed('nsmallest_shapes', NSMALLEST, expected)
        self._both('nsmallest_shapes', NSMALLEST, expected)

    def test_nsmallest_of_tuples_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-s2-') as tmp:
            source = Path(tmp) / 'nsmallest_tuples.py'
            source.write_text(NSMALLEST_TUPLES, encoding='utf8')
            result, exe = build_source(tmp, 'nsmallest_tuples', source)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('heapq.nsmallest()', result.stderr)

    def test_berth_sim_is_typed(self):
        source = REPO / 'lab' / 'compare' / 'src' / 'berth_sim' / 'main.py'
        with tempfile.TemporaryDirectory(prefix='ail-s2-') as tmp:
            result, exe = build_source(tmp, 'berth_sim', source)
            self.assertEqual(result.returncode, 0, result.stderr[-4000:])


if __name__ == '__main__':
    unittest.main()
