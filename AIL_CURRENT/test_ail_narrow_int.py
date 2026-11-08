"""fbnarrow3: `AIL_NARROW_INT=1` stores some `list[int]` locals and class fields as `ail_ilist`.

A list is narrowed only when every use of it is one of `.append`, `len`, an int index read or
write, `for v in`, `.pop()`, `.clear()`, a whole store into a field/local of the same kind, or a
pass to another narrowed list. A value outside int32 widens the list at run time instead of
truncating it; the emitted C without the variable is byte-identical to before.

Every program below is built with the variable unset, set, and on the general path
(`AIL_UNIFIED_FORCE=1`), and compared with CPython. Two behaviours are identical on the base and
are compared across the AIL builds only: CPython's "list assignment index out of range" text (AIL
says "list index out of range" everywhere), and an int64 overflow inside `try` on the default
typed path (the base build stops the same way).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AIL = ROOT / 'ail_chatgpt.py'
HAVE_CC = bool(shutil.which('gcc') or shutil.which('cc'))

MODES = (('default', {}), ('narrow', {'AIL_NARROW_INT': '1'}), ('force', {'AIL_UNIFIED_FORCE': '1'}))

BOUNDS = '''def main() -> None:
    xs: list[int] = []
    for v in (2147483647, 2147483648, -2147483648, -2147483649, 0, 5):
        xs.append(v)
    print(len(xs))
    for i in range(len(xs)):
        print(xs[i])
    print(xs[-1], xs[-6])
    xs[0] = -2147483649
    xs[3] = 2147483648
    print(xs[0], xs[3])

main()
'''

INT64 = '''def main() -> None:
    xs: list[int] = []
    xs.append(9223372036854775807)
    xs.append(-9223372036854775808)
    print(xs[0], xs[1])
    print(xs[0] + xs[1])
    print(len(xs))

main()
'''

OVERFLOW = '''def main() -> None:
    xs: list[int] = []
    xs.append(9223372036854775807)
    print(len(xs))
    xs.append(xs[0] + 1)

main()
'''

FIELD = '''class T:
    def __init__(self) -> None:
        self.w: list[int] = []

    def widen(self) -> None:
        self.w.append(2147483648)

    def read(self, i: int) -> int:
        return self.w[i]

    def total(self) -> int:
        t = 0
        for v in self.w:
            t += v
        return t


def main() -> None:
    t = T()
    t.w.append(1)
    t.w.append(2147483647)
    print(len(t.w), t.read(0), t.read(1))
    t.widen()
    print(len(t.w), t.read(2), t.total())
    t.w[0] = -2147483649
    print(t.read(0))
    for v in t.w:
        print(v)
    print(len(t.w))

main()
'''

NEGATIVE = '''def main() -> None:
    xs: list[int] = []
    for i in range(5):
        xs.append(i * 3)
    print(xs[-1], xs[-5], xs[len(xs) - 1])
    xs[-1] = 99
    xs[-5] = -99
    print(xs[0], xs[4])
    for v in xs:
        print(v)

main()
'''

INDEX = '''def main() -> None:
    xs: list[int] = []
    print(len(xs))
    try:
        xs.pop()
    except IndexError as e:
        print("pop-empty", e)
    for i in range(3):
        xs.append(i)
    try:
        print(xs[3])
    except IndexError as e:
        print("read", e)
    try:
        print(xs[-4])
    except IndexError as e:
        print("read-neg", e)
    try:
        xs.pop(5)
    except IndexError as e:
        print("pop-bad", e)
    print(xs.pop(1), len(xs), xs[0], xs[1])
    xs.clear()
    print(len(xs))

main()
'''

TWO_CALLS = '''def inner(xs: list[int]) -> int:
    t = 0
    for v in xs:
        t += v
    return t


def outer(xs: list[int]) -> int:
    xs.append(100)
    return inner(xs) + len(xs)


def main() -> None:
    xs: list[int] = []
    for i in range(4):
        xs.append(i)
    print(outer(xs))
    print(inner(xs))
    print(len(xs), xs[0], xs[-1])

main()
'''

SLICE = '''def main() -> None:
    xs: list[int] = []
    for v in (1, 2147483647, 2147483648, -2147483649, 7, 9):
        xs.append(v)
    a = xs[1:4]
    for v in a:
        print(v)
    b = xs[:]
    for v in b:
        print(v)
    c = xs[::2]
    for v in c:
        print(v)
    d = xs[::-1]
    for v in d:
        print(v)
    e = xs[2:]
    for v in e:
        print(v)
    f = xs[:2]
    for v in f:
        print(v)
    g = xs[-3:-1]
    for v in g:
        print(v)
    h = xs[0:0]
    print(len(h))
    ys = xs[1:5:2]
    print(len(ys), ys[0], ys[1])
    print(xs[0], xs[1], xs[2], xs[3], xs[4], xs[5])

main()
'''

COPY = '''def main() -> None:
    xs: list[int] = []
    for v in (2147483647, 2147483648, -2147483649, 0):
        xs.append(v)
    ys = xs.copy()
    print(len(ys))
    for v in ys:
        print(v)
    ys[0] = 5
    print(xs[0], ys[0])
    zs = list(xs)
    for v in zs:
        print(v)
    ws = xs + ys
    print(len(ws))
    for v in ws:
        print(v)
    es: list[int] = []
    t = es.copy()
    print(len(t))
    u = list(es)
    print(len(u))
    w = es + es
    print(len(w))

main()
'''

SORT = '''def main() -> None:
    xs: list[int] = []
    for v in (5, 2147483648, -3, 2147483647, -2147483649, 0):
        xs.append(v)
    xs.sort()
    for v in xs:
        print(v)
    ys = sorted(xs)
    for v in ys:
        print(v)
    print(len(xs))
    es: list[int] = []
    es.sort()
    q = sorted(es)
    print(len(q))

main()
'''

KEYSORT = '''def main() -> None:
    key: list[int] = []
    for v in (5, 3, 5, 3, 5, 3):
        key.append(v)
    idx: list[int] = []
    for i in range(len(key)):
        idx.append(i)
    idx.sort(key=lambda i: key[i])
    print(idx)
    order = sorted(idx, key=lambda i: key[i])
    print(order)

main()
'''

EMPTY = '''def main() -> None:
    xs: list[int] = []
    print(len(xs))
    for v in xs:
        print(v)
    xs.append(7)
    print(len(xs), xs[0])
    xs.clear()
    print(len(xs))
    ys: list[int] = []
    zs: list[int] = []
    print(len(ys) + len(zs))

main()
'''


def build(directory, name, source, tag, env_extra):
    path = Path(directory, name + '.py')
    path.write_text(source)
    exe = Path(directory, '%s.%s' % (name, tag))
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_NARROW_INT', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    env.update(env_extra)
    built = subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(path), '-o', str(exe)],
                           capture_output=True, text=True, timeout=600, env=env)
    return built, exe


def run(exe):
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def cpython(directory, name, source):
    path = Path(directory, name + '.py')
    path.write_text(source)
    r = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class NarrowIntTests(unittest.TestCase):
    maxDiff = None

    def check(self, name, source, cpython_exact=True):
        with tempfile.TemporaryDirectory() as tmp:
            results = {}
            for tag, env in MODES:
                built, exe = build(tmp, name, source, tag, env)
                self.assertEqual(built.returncode, 0, '%s build of %s failed:\n%s%s'
                                 % (tag, name, built.stdout, built.stderr))
                results[tag] = run(exe)
            ref = cpython(tmp, name, source)
            for tag in ('default', 'narrow', 'force'):
                rc, out, err = results[tag]
                self.assertEqual((rc, out), (results['default'][0], results['default'][1]),
                                 '%s differs from the default build for %s\n%s' % (tag, name, err))
            if cpython_exact:
                self.assertEqual((results['narrow'][0], results['narrow'][1]), (ref[0], ref[1]),
                                 '%s vs CPython\n%s' % (name, results['narrow'][2]))
            return results, ref

    def test_int32_boundaries(self):
        self.check('bounds', BOUNDS)

    def test_int64_limits(self):
        self.check('int64', INT64)

    def test_beyond_int64_stops_loudly(self):
        results, ref = self.check('overflow', OVERFLOW, cpython_exact=False)
        rc, out, err = results['narrow']
        self.assertEqual(rc, 1)
        self.assertEqual(out, results['default'][1])
        self.assertIn('OverflowError: integer overflow in +', err)
        self.assertEqual(err, results['default'][2])

    def test_field_widened_in_one_function_read_in_another(self):
        self.check('field', FIELD)

    def test_negative_indexes(self):
        self.check('negative', NEGATIVE)

    def test_index_errors(self):
        self.check('index', INDEX)

    def test_list_through_two_calls(self):
        self.check('two_calls', TWO_CALLS)

    def test_empty_list(self):
        self.check('empty', EMPTY)

    def test_slices_across_int32_boundary(self):
        self.check('slice', SLICE)

    def test_copy_and_concatenate(self):
        self.check('copy', COPY)

    def test_sort_of_widened_list(self):
        self.check('sort', SORT)

    def test_key_sort_equal_keys_are_stable(self):
        self.check('keysort', KEYSORT)

    def test_write_index_text_matches_across_builds(self):
        source = ('def main() -> None:\n    xs: list[int] = []\n    xs.append(1)\n'
                  '    try:\n        xs[3] = 1\n    except IndexError as e:\n        print(e)\n\nmain()\n')
        results, _ = self.check('write_index', source, cpython_exact=False)
        self.assertEqual(results['narrow'][1].strip(), 'list index out of range')
        self.assertEqual(results['narrow'][1], results['default'][1])


if __name__ == '__main__':
    unittest.main()
