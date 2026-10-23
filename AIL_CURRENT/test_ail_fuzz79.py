"""Differential round 79: the old __getitem__ sequence protocol when iterating.

Found with small programs in the "class inheritance from builtins" area (a class
with __getitem__, and a subclass overriding it with super().__getitem__), compared
against CPython on both builds.  CPython iterates an instance with __getitem__ but
no __iter__ by calling __getitem__(0), __getitem__(1), ... until IndexError.  The
general path's ail__iter_inst only knew __iter__/__next__, so `list(s)`, a `for`
loop, a comprehension, `tuple(s)`, `sum(s)`, `min`/`max`, `sorted`, `in`, zip,
enumerate, unpacking and `iter(s)` all stopped with

    TypeError: 'instance' object is not iterable

on both builds (the typed path refused the program and the default build fell
back to the general path).  Nothing was printed where CPython prints the items.

The general runtime now gives such an instance an AIL_IT_SEQGET iterator that
calls __getitem__ with 0, 1, ... and stops on an IndexError or StopIteration
(other exceptions still propagate), and remembers exhaustion so a later next()
does not call __getitem__ again, matching CPython's sequence iterator.  __iter__
still wins when a class defines both, and an inherited __getitem__ is found
through the base classes.  An __iter__ that returns self without a __next__ is
not an iterator: it raises TypeError instead of falling back to __getitem__.
The programs below compare stdout and the exit code with CPython on the forced
general build and on the default build.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BASIC = r'''class Seq:
    def __init__(self, xs):
        self.xs = xs

    def __len__(self):
        return len(self.xs)

    def __getitem__(self, i):
        if i >= len(self.xs):
            raise IndexError
        return self.xs[i]


def main():
    s = Seq([10, 20, 30])
    print(s[1])
    print(list(s))
    print(20 in s, 99 in s)
    print(sum(s))
    print("done")


main()
'''

CONSUMERS = r'''class Seq:
    def __init__(self, n):
        self.n = n
        self.calls = []

    def __len__(self):
        return self.n

    def __getitem__(self, i):
        self.calls.append(i)
        if i >= self.n:
            raise IndexError("done")
        return i * 10


def main():
    s = Seq(3)
    print(list(s), s.calls)
    print(tuple(s), sum(s), min(s), max(s), sorted(s))
    print([x for x in s])
    print(20 in s, 99 in s, 0 in s)
    print(list(zip(s, "abc")))
    print(list(enumerate(s)))
    a, b, c = s
    print(a, b, c, [*s])

    total = 0
    for x in s:
        total += x
    print(total)
    print("done")


main()
'''

INHERIT = r'''class Seq:
    def __init__(self, xs):
        self.xs = xs

    def __len__(self):
        return len(self.xs)

    def __getitem__(self, i):
        return self.xs[i]


class Sub(Seq):
    def __getitem__(self, i):
        return super().__getitem__(i)


def main():
    for xs in ([], [0], [1, 2], [10, 20, 30]):
        s = Sub(xs)
        print(len(s), list(s), tuple(s), sum(s))
        for x in s:
            print(x, end=" ")
        print()
        if xs:
            print(s[0], s[-1])
    print("done")


main()
'''

DETAILS = r'''class Seq:
    def __init__(self, n, bad=-1):
        self.n = n
        self.bad = bad
        self.calls = []

    def __getitem__(self, i):
        self.calls.append(i)
        if i >= self.n:
            raise IndexError("done")
        if i == self.bad:
            raise ValueError("bad item")
        return i + 1


class Both(Seq):
    def __iter__(self):
        return iter([100, 200])


def main():
    s = Seq(3)
    it = iter(s)
    print(next(it), next(it), next(it))
    try:
        next(it)
    except StopIteration:
        print("stop")
    try:
        next(it)
    except StopIteration:
        print("stop again")
    print(s.calls)

    e = Seq(3, bad=1)
    try:
        print(list(e))
    except ValueError as ex:
        print("ValueError", ex)
    print(e.calls)

    print(list(Both(5)), Both(5).calls)
    print(list(iter(Both(5))))
    print("done")


main()
'''

ITERSELF = r'''class C:
    def __iter__(self):
        return self

    def __getitem__(self, i):
        if i >= 2:
            raise IndexError
        return i


class Sub(C):
    pass


def main():
    try:
        print(list(C()))
    except TypeError as e:
        print("TypeError", e)
    try:
        it = iter(C())
        print("iter ok")
        print(next(it))
    except TypeError as e:
        print("TypeError2", e)
    try:
        print([x for x in Sub()])
    except TypeError as e:
        print("TypeError3", e)
    print("done")


main()
'''

STOPITER_PARTIAL = r'''class S:
    def __init__(self, n):
        self.n = n

    def __getitem__(self, i):
        if i >= self.n:
            raise StopIteration
        return i * 10


class MyStop(StopIteration):
    pass


class S2:
    def __getitem__(self, i):
        if i >= 2:
            raise MyStop("end")
        return i


def main():
    for x in S(3):
        print(x)
    print("after")
    for x in iter(S(3)):
        print("n", x)
    print(list(S(0)))
    print(list(S2()))
    it = iter(S(3))
    print(next(it), next(it), next(it))
    try:
        next(it)
    except StopIteration:
        print("stop")
    try:
        next(it)
    except StopIteration:
        print("stop again")
    print("done")


main()
'''

CASES = [
    ('basic', BASIC),
    ('consumers', CONSUMERS),
    ('inherit', INHERIT),
    ('details', DETAILS),
    ('iterself', ITERSELF),
    ('stopiter_partial', STOPITER_PARTIAL),
]


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


class Fuzz79Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz79-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_basic(self):
        self.check('basic', BASIC)

    def test_consumers(self):
        self.check('consumers', CONSUMERS)

    def test_inherited_getitem(self):
        self.check('inherit', INHERIT)

    def test_protocol_details(self):
        self.check('details', DETAILS)

    def test_iter_returning_self_without_next(self):
        self.check('iterself', ITERSELF)

    def test_stopiteration_ends_sequence(self):
        self.check('stopiter_partial', STOPITER_PARTIAL)


if __name__ == '__main__':
    unittest.main()
