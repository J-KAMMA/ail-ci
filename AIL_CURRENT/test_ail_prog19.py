"""prog19 typed reach: `dx, dy = random.choice(moves)` on the typed path, against CPython 3.12.

The tuple pass runs before the random lowering. It used to leave this unpack untouched because
`random.choice(seq)` had no element type, so the later lowering turned the call into
`seq[<index>]` and the typed emitter saw an opaque subscript instead of a row.  The tuple pass now
types `random.choice` as the list's element type (for `import random` and `from random import
choice`), so the unpack lowers to one row read and field reads.

T1  the program `g11_018` shape (a fixed-seed random walk over a list of int tuples) takes the
    typed path, with both AIL_IR settings and the default build, and prints CPython's bytes.
T2  the same shape through a list parameter, an alias and a `from random import choice` call.
T3  boundaries: zero steps, negative coordinates, an empty list (CPython's IndexError), and a
    float tuple; a scalar list (`list[int]` / `list[str]`) is unchanged.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

WALK = '''import random
import math
from typing import Tuple


def simulate_random_walk(steps: int, seed: int) -> Tuple[Tuple[int, int], float]:
    random.seed(seed)
    moves: list[Tuple[int, int]] = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    x, y = 0, 0
    max_distance: float = 0.0
    for _ in range(steps):
        dx, dy = random.choice(moves)
        x += dx
        y += dy
        distance = math.hypot(x, y)
        if distance > max_distance:
            max_distance = distance
    return (x, y), max_distance


def main() -> None:
    final_position, max_distance = simulate_random_walk(1000, 42)
    print(f"Final position: {final_position}")
    print(f"Maximum distance from origin: {max_distance:.4f}")
    print(simulate_random_walk(0, 7))


main()
'''

PARAM = '''import random
from random import choice, seed
from typing import Tuple


def walk(moves: list[Tuple[int, int]], steps: int, seed_value: int) -> Tuple[int, int]:
    seed(seed_value)
    x, y = 0, 0
    for _ in range(steps):
        dx, dy = choice(moves)
        x += dx
        y += dy
    return x, y


def main() -> None:
    ms: list[Tuple[int, int]] = [(2, -3), (-4, 5), (0, 0)]
    alias = ms
    print(walk(ms, 0, 1))
    print(walk(ms, 10, 2))
    print(walk(alias, 10, 2), ms)
    print(walk([(-1, -1), (1, 1)], 9, 4))


main()
'''

BOUNDARIES = '''import random
from typing import Tuple


def pick(xs: list[Tuple[int, int]]) -> int:
    a, b = random.choice(xs)
    return a + b


def main() -> None:
    random.seed(5)
    print(pick([(5, -9)]), pick([(-2, -3), (4, 6)]))
    empty: list[Tuple[int, int]] = []
    try:
        print(pick(empty))
    except IndexError as exc:
        print(type(exc).__name__, exc)
    fs: list[Tuple[float, float]] = [(1.5, -2.25), (0.0, 3.0)]
    a, b = random.choice(fs)
    print(a, b, a + b)
    scalars: list[int] = [-5, 0, 7]
    words: list[str] = ["a", "bb", ""]
    for _ in range(8):
        print(random.choice(scalars), random.choice(words), end=';')
    print()


main()
'''


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog19(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog19_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def cpython(self, text, name):
        path = Path(self.tmp) / (name + '_py.py')
        path.write_text(text, encoding='utf-8')
        return subprocess.run([sys.executable, '-B', str(path)], capture_output=True,
                              text=True, timeout=300, encoding='utf-8')

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

    def same(self, text, name, typed):
        want = self.cpython(text, name)
        for ir in ('0', '1'):
            built, exe = self.build(text, name, ir, typed)
            self.assertEqual(built.returncode, 0, 'typed=%s IR=%s: %s' % (typed, ir, built.stderr[-2000:]))
            if typed:
                self.assertNotIn('built on the general path', built.stderr, 'IR=%s' % ir)
            got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, encoding='utf-8')
            self.assertEqual(got.stdout, want.stdout, 'typed=%s IR=%s' % (typed, ir))
            self.assertEqual(got.returncode, want.returncode, 'typed=%s IR=%s' % (typed, ir))
        return want

    def test_random_walk_is_typed(self):
        self.same(WALK, 'walk', True)
        self.same(WALK, 'walk_default', False)

    def test_parameter_alias_and_from_import(self):
        self.same(PARAM, 'param', True)

    def test_boundaries(self):
        self.same(BOUNDARIES, 'bounds', True)


if __name__ == '__main__':
    unittest.main()
