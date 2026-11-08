"""`xs[i] op= v` on a list element with a negative index stays inside the list (job augidx1).

The IR lowered `c[i] op= v` as a checked read and an UNCHECKED write at the raw index (ir/lower.py, aug_target). The
checked read accepts a negative index by normalising it inside the helper, so the write stored at `p[-1]`, before
the buffer: `out[-1] += 1` in a typed function corrupted the heap and the default build aborted with
`free(): invalid pointer` / `munmap_chunk(): invalid pointer` (AIL_UNIFIED_FORCE=1 and CPython were right). The write
now takes the read's mode. When the right-hand side has no call, the read normalises and checks the index once into
a C local and the write stores at that local (no second check); with a call in between (which may resize the list)
the write is checked again against the length at the time of the store, as CPython's list_ass_item does. The index
expression is evaluated once.

Each program is built twice (the default build, and the default build with AIL_UNIFIED_FORCE=1) and must print
CPython's stdout byte for byte with CPython's exit status: int and float lists, `xs[-1] += 1`, `xs[-len(xs)] -= 2`,
an index from a parameter, an index with a side effect (evaluated once), nested `m[-1][-1] *= 3`, out-of-range
negative and positive indexes (IndexError, exit 1, nothing printed after it), a right-hand side that shrinks the
list, and lists of str, of objects and of mixed values.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = str(ROOT / 'python' / 'pkg-v12' / 'pyc.py')

INRANGE = '''\
class Counter:
    def __init__(self) -> None:
        self.n = 0


def ints(n: int) -> int:
    out = [0] * 4
    for k in range(n):
        out[-1] += 1
        out[-len(out)] -= 2
        out[k % 4 - 4] += k
    out[-2] *= 3
    out[-3] |= 6
    out[-3] <<= 2
    out[-1] //= 3
    return out[0] * 1000000 + out[1] * 10000 + out[2] * 100 + out[3]


def floats(n: int) -> float:
    f = [0.5] * 3
    for k in range(n):
        f[-1] += 1.25
        f[-len(f)] -= 0.5
        f[-2] *= 1.5
    f[-1] /= 4.0
    return f[0] * 1000.0 + f[1] + f[2]


def at(i: int, v: int) -> int:
    out = [10, 20, 30, 40]
    out[i] += v
    out[i] -= 1
    return out[0] + out[1] * 100 + out[2] * 10000 + out[3] * 1000000


def fat(i: int, v: float) -> float:
    f = [1.0, 2.0, 3.0]
    f[i] *= v
    return f[0] + f[1] * 10.0 + f[2] * 100.0


def once(c: Counter) -> int:
    c.n += 1
    return c.n - 4


def side(m: int) -> int:
    c = Counter()
    out = [0] * 4
    for k in range(m):
        out[once(c)] += 7
    return out[0] + out[1] * 100 + out[2] * 10000 + out[3] * 1000000 + c.n * 100000000


def nested(n: int) -> int:
    m = [[1, 2, 3], [4, 5, 6]]
    for k in range(n):
        m[-1][-1] *= 3
        m[-2][-len(m[0])] += 1
        m[k % 2 - 2][-2] -= k
    return m[0][0] + m[0][1] * 100 + m[1][1] * 10000 + m[1][2] * 1000000


def fnested(n: int) -> float:
    m = [[1.5, 2.5], [3.5, 4.5]]
    for k in range(n):
        m[-1][-1] *= 3.0
        m[-2][-2] += 0.25
    return m[0][0] + m[1][1]


def main() -> None:
    print(ints(10))
    print(floats(5))
    for i in (-1, -2, -3, -4, 0, 3):
        print(at(i, 5), fat(i % 3 - 3, 2.5))
    print(side(4))
    print(nested(4))
    print(fnested(3))


main()
'''

RANGE = '''\
import sys


def at(i: int, v: int) -> int:
    out = [10, 20, 30, 40]
    out[i] += v
    return out[0] + out[3]


def fat(i: int, v: float) -> float:
    f = [1.0, 2.0, 3.0]
    f[i] *= v
    return f[0] + f[2]


def loop(i: int, n: int) -> int:
    out = [0] * 3
    t = 0
    for k in range(n):
        out[i - k] += 1
        t += out[0]
    return t


def main() -> None:
    i = int(sys.stdin.readline())
    print(at(i, 5))
    print(fat(i + 1, 2.0))
    print(loop(i + 4, 3))
    print('end')


main()
'''

OBJECTS = '''\
class Item:
    def __init__(self, n: int) -> None:
        self.n = n


def main() -> None:
    words = ['a', 'b', 'c']
    for k in range(3):
        words[-1] += 'x'
        words[-len(words)] += str(k)
    print(words)
    mixed = [1, 'p', 2.5, [7]]
    mixed[-4] += 10
    mixed[-3] += 'q'
    mixed[-2] *= 2
    mixed[-1] += [8]
    print(mixed)
    items = [Item(1), Item(2)]
    items[-1].n += 5
    items[-2].n -= 3
    print(items[0].n, items[1].n)
    grid = [['a', 'b'], ['c', 'd']]
    grid[-1][-1] *= 3
    print(grid)
    try:
        words[-4] += 'z'
    except IndexError as e:
        print('IndexError', e)
    try:
        mixed[-5] += 1
    except IndexError as e:
        print('IndexError', e)
    xs = [1, 2, 3]
    try:
        xs[-4] += 1
    except IndexError as e:
        print('IndexError', e)
    fs = [1.5]
    try:
        fs[-2] -= 1.0
    except IndexError as e:
        print('IndexError', e)
    print(xs, fs)


main()
'''

SHRINK = '''\
import sys


class Box:
    def __init__(self) -> None:
        self.v: list[int] = [1, 2, 3, 4]
        self.f: list[float] = [1.5, 2.5, 3.5]


def shrink(b: Box) -> int:
    b.v.pop()
    return 10


def fshrink(b: Box) -> float:
    b.f.pop()
    return 0.25


def main() -> None:
    k = int(sys.stdin.readline())
    b = Box()
    b.v[-1] += shrink(b)
    print(b.v)
    b.f[-2] += fshrink(b)
    print(b.f)
    b.v[k] += shrink(b)
    print(b.v)
    print('end')


main()
'''


def _env(force):
    env = dict(os.environ, AIL_SURFACE='python', PYTHONUTF8='1')
    for name in ('AIL_IR', 'AIL_NO_MIX', 'AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE'):
        env.pop(name, None)
    if force:
        env['AIL_UNIFIED_FORCE'] = '1'
    return env


class AugIndex(unittest.TestCase):
    def check(self, name, text, stdins=('',), typed=False):
        with tempfile.TemporaryDirectory(prefix='ail-augidx-') as directory:
            src = Path(directory) / (name + '.py')
            src.write_text(text, encoding='utf-8')
            want = {}
            for stdin in stdins:
                done = subprocess.run([sys.executable, '-B', str(src)], input=stdin.encode(), capture_output=True,
                                      timeout=120, env=_env(False))
                want[stdin] = (done.stdout.replace(b'\r\n', b'\n'), done.returncode)
            for force in (False, True):
                exe = Path(directory) / ('exe_%s_%d' % (name, force))
                built = subprocess.run([sys.executable, '-B', PYC, str(exe), '--file', str(src)], cwd=directory,
                                       capture_output=True, text=True, timeout=900, env=_env(force))
                self.assertEqual(built.returncode, 0, (name, force, (built.stdout + built.stderr)[-1500:]))
                if typed and not force:
                    self.assertNotIn('general path', built.stderr, name)
                for stdin in stdins:
                    done = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=60,
                                          cwd=directory)
                    got = (done.stdout.replace(b'\r\n', b'\n'), done.returncode)
                    self.assertEqual(got, want[stdin], (name, force, stdin, done.stderr[-600:]))

    def test_negative_indexes_in_range(self):
        self.check('augidx_inrange', INRANGE, typed=True)

    def test_out_of_range_raises_like_cpython(self):
        self.check('augidx_range', RANGE, stdins=('-1\n', '-4\n', '-5\n', '3\n', '4\n'), typed=True)

    def test_right_hand_side_shrinks_the_list(self):
        """A call between the read and the write may pop the list: the write is checked again at the store."""
        self.check('augidx_shrink', SHRINK, stdins=('1\n', '2\n', '-3\n', '0\n'), typed=True)

    def test_object_lists(self):
        self.check('augidx_objects', OBJECTS)

    def test_no_unchecked_store_at_a_negative_constant(self):
        """The C of the typed program never writes `p[-k]` (the old store before the buffer)."""
        with tempfile.TemporaryDirectory(prefix='ail-augidx-') as directory:
            src = Path(directory) / 'augidx_c.py'
            src.write_text(INRANGE, encoding='utf-8')
            done = subprocess.run([sys.executable, '-B', PYC, str(Path(directory) / 'exe'), '--file', str(src),
                                   '--emit-c'], cwd=directory, capture_output=True, text=True, timeout=900,
                                  env=_env(False))
            self.assertEqual(done.returncode, 0, done.stderr[-1500:])
            # the read normalises and checks the index once into a local; the paired write stores there
            self.assertRegex(done.stdout, r'int64_t (augj\d+) = -1LL;')
            self.assertRegex(done.stdout, r'p\[augj\d+\] = ')
            self.assertNotRegex(done.stdout, r'p\[-\d+LL\] = ')


if __name__ == '__main__':
    unittest.main()
