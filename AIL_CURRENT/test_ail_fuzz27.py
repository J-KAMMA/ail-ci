"""Differential round 27: a set's pop cursor must move with the body it indexes.

The general (boxed) runtime keeps a set's elements in insertion order and a `fin`
cursor for `pop()`. `symmetric_difference_update`, `intersection_update`, `^=` and
`&=` replace the body through `ail_setx_swap_bodies`, which swapped the entries,
sizes and index but not `fin`. A set that had already popped something kept the old
cursor into the new body, so the next `pop()` skipped the first remaining element
and could then walk past the live entries (`{1,2,3}.pop(); s.symmetric_difference_update(set());
s.pop()` printed 3 instead of CPython's 2). The typed path was unaffected.

The programs below keep that shape for a literal set and for a set reached through a
function argument, a list item, an attribute and a dict value, on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BASIC = r'''def main() -> None:
    s: set[int] = {1, 2, 3}
    print(s.pop())
    s.symmetric_difference_update(set())
    print(s.pop())
    print(len(s), 2 in s, 3 in s)
    t: set[int] = {10, 20, 30}
    print(t.pop())
    t.intersection_update({20, 30, 40})
    print(t.pop())
    print(len(t), 20 in t, 30 in t)


main()
'''

OPERATORS = r'''def main() -> None:
    s: set[int] = {1, 2, 3, 4}
    print(s.pop())
    s ^= {4, 5}
    print(s.pop(), len(s), 2 in s, 3 in s, 4 in s, 5 in s)
    t: set[int] = {1, 2, 3, 4}
    print(t.pop())
    t &= {2, 3, 4, 9}
    print(t.pop(), len(t), 2 in t, 3 in t, 4 in t, 9 in t)
    u: set[int] = {1, 2, 3, 4}
    print(u.pop())
    u.intersection_update([2, 3])
    out: list[int] = []
    while len(u) > 0:
        out.append(u.pop())
    out.sort()
    print(out, len(u))
    v: set[int] = {1}
    print(v.pop(), len(v))
    v.symmetric_difference_update({7})
    print(v.pop(), len(v))
    w: set[int] = {1, 2}
    print(w.pop())
    w.intersection_update(set())
    print(len(w))
    try:
        w.pop()
    except KeyError as e:
        print("empty", e)


main()
'''

SOURCES = r'''class Box:
    pass


def mutate(s: set[int]) -> None:
    s.symmetric_difference_update(set())
    print(s.pop(), len(s), 2 in s, 3 in s)


def main() -> None:
    b = Box()
    b.s = {1, 2, 3}
    print(b.s.pop())
    b.s.symmetric_difference_update(set())
    print(b.s.pop(), len(b.s), 2 in b.s, 3 in b.s)
    b.s.intersection_update({3, 4})
    print(b.s.pop(), len(b.s))
    xs: list = [{1, 2, 3}]
    s = xs[0]
    print(s.pop())
    s.symmetric_difference_update(set())
    print(s.pop(), len(s), 2 in s, 3 in s, len(xs[0]), 2 in xs[0])
    d: dict = {"s": {10, 20, 30}}
    q = d["s"]
    print(q.pop())
    q.symmetric_difference_update(set())
    print(q.pop(), len(q), 20 in q, 30 in q, len(d["s"]), 20 in d["s"])
    r: set[int] = {4, 5, 6}
    print(r.pop())
    mutate(r)
    print(len(r))


main()
'''

LARGE = r'''def main() -> None:
    s: set[int] = set()
    for i in range(-50, 50):
        s.add(i)
    for i in range(5):
        s.discard(i)
        s.add(i - 100)
    first: int = 0
    total: int = 0
    for i in range(3):
        first += 1
        total += s.pop()
    s.symmetric_difference_update(set())
    rest: int = 0
    lo: int = 1000
    hi: int = -1000
    while len(s) > 0:
        v: int = s.pop()
        rest += 1
        total += v
        if v < lo:
            lo = v
        if v > hi:
            hi = v
    print(first + rest, total, lo, hi)
    t: set[int] = set()
    for i in range(20):
        t.add(i)
    for i in range(5):
        t.pop()
    t.intersection_update({i for i in range(5, 20)})
    n: int = 0
    tot: int = 0
    while len(t) > 0:
        tot += t.pop()
        n += 1
    print(n, tot)


main()
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


class Fuzz27Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz27-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_pop_cursor_after_swap(self):
        self.check('swap_basic', BASIC)

    def test_pop_cursor_after_inplace_operators(self):
        self.check('swap_operators', OPERATORS)

    def test_pop_cursor_through_sources(self):
        self.check('swap_sources', SOURCES)

    def test_pop_cursor_large_set(self):
        self.check('swap_large', LARGE)


if __name__ == '__main__':
    unittest.main()
