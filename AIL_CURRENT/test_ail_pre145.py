"""Counter repr order with counts that are not numbers (pre-existing difference from pre120).

CPython's Counter.__repr__ prints the entries by count, the largest first, and its sort
accepts any counts that `<` orders. AIL's repr sorter only handled numbers (and, on the
pre120 tree, str), so a Counter whose counts are lists, tuples, bytes or bytearrays kept
insertion order. The comparator now orders those values (and str, and nested lists/tuples)
on both builds; equal counts keep insertion order like CPython's stable reverse sort.

Counts are installed by item assignment: `Counter(mapping)` with non-int values is a
separate, older difference (the mapping constructor still adds `0 + value` on this tree).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REPR_SHAPES = r'''from collections import Counter


def mk(pairs):
    c = Counter()
    for k, v in pairs:
        c[k] = v
    return c


cases = [
    ("list", [("a", [1]), ("b", [2])]),
    ("listrev", [("a", [2]), ("b", [1])]),
    ("tuple", [("a", (1,)), ("b", (2,))]),
    ("tuplelen", [("a", (1,)), ("b", (1, 0))]),
    ("bytes", [("a", b"x"), ("b", b"y")]),
    ("bytearray", [("a", bytearray(b"y")), ("b", bytearray(b"x"))]),
    ("str", [("a", "x"), ("b", "y")]),
    ("nested", [("a", [[1], [2]]), ("b", [[2], [1]])]),
    ("liststr", [("a", ["x"]), ("b", ["y"])]),
    ("float", [("a", 1.5), ("b", 2.5)]),
    ("intfloat", [("a", 1), ("b", 2.0)]),
    ("bool", [("a", True), ("b", False)]),
    ("emptyseq", [("a", []), ("b", [0])]),
    ("equal", [("a", [1]), ("b", [1]), ("c", [0])]),
    ("neg", [("a", [-1]), ("b", [-2])]),
    ("wide", [("a", 2 ** 40), ("b", -2 ** 40)]),
]
for label, pairs in cases:
    c = mk(pairs)
    print(label, c)
    print(label, "mc", c.most_common())
'''

REPR_ROUTES = r'''from collections import Counter


class Box:
    def __init__(self, v):
        self.v = v


def build(a, b):
    c = Counter()
    c["x"] = a
    c["y"] = b
    return c


vals = [[1], [2]]
d = {"lo": [0], "hi": [3]}
box = Box([9])
print("arg", build([1], [2]))
print("listitem", build(vals[0], vals[1]))
print("attr", build(box.v, [[8]][0]))
print("dictval", build(d["lo"], d["hi"]))
print("tuplearg", build((1,), (2,)))
print("plaindict", {"a": [1], "b": [2]})
print("itercounter", Counter([1, 1, 2]))
c = Counter()
c["p"] = [5]
c["q"] = [4]
print("listof", [c, c])
shared = [1]
d2 = Counter()
d2["a"] = shared
d2["b"] = [2]
print("before", d2)
shared.append(9)
print("after", d2)
'''


REPR_FALLBACK = r'''from collections import Counter


def mk(pairs):
    c = Counter()
    for k, v in pairs:
        c[k] = v
    return c


# an unorderable pair makes CPython's repr fall back to insertion order (its sort raises,
# the TypeError is caught); the sorter must not order the pairs that do compare.
cases = [
    ("late", [("a", [0, 0]), ("b", ["x", 1])]),
    ("late_rev", [("a", ["x", 1]), ("b", [0, 0])]),
    ("listtuple", [("a", [1]), ("b", (1,))]),
    ("strint", [("a", "x"), ("b", 1)]),
    ("prefix", [("a", [1]), ("b", [1, "x"])]),
    ("deep", [("a", [[1], 0]), ("b", [[1], "x"])]),
    ("same", [("a", [1, "x"]), ("b", [1, "y"])]),
    ("allnums", [("a", [1, 2]), ("b", [1, 3])]),
]
for label, pairs in cases:
    try:
        print(label, mk(pairs))
    except Exception as e:
        print(label, type(e).__name__, e)
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre145Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre145-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_counter_repr_orders_sequence_and_bytes_counts(self):
        self.check('counter_repr_shapes', REPR_SHAPES)

    def test_counter_repr_counts_through_routes_and_after_mutation(self):
        self.check('counter_repr_routes', REPR_ROUTES)

    def test_counter_repr_falls_back_on_unorderable_counts(self):
        self.check('counter_repr_fallback', REPR_FALLBACK)


if __name__ == '__main__':
    unittest.main()
