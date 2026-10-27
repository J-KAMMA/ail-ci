"""any()/all() over a generator expression stop at the decisive element (CPython 3.12).

The fused general-path emitter used to walk every element even when the answer was
already known, so `any(hit(log, a, b) for a, b in pairs)` called hit() for every pair.
It now leaves the generator loops at the first truthy (any) / falsy (all) element.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
HAVE_CC = shutil.which('gcc') is not None
sys.path.insert(0, str(ROOT))


def surface(text):
    import ail_syntax
    return ail_syntax.fold_constants(ail_syntax.python_surface(text))


def build_general(directory, text, name):
    source, exe = Path(directory, name + '_g.ail'), Path(directory, name + '_g')
    source.write_text(surface(text), encoding='utf-8')
    env = dict(os.environ, AIL_IR='0', AIL_NO_CACHE='1', AIL_SURFACE='python')
    env.pop('AIL_NO_GENERAL', None)
    res = subprocess.run([sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only'],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe


def build_default(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_d')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR='0')
    env.pop('AIL_NO_GENERAL', None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax',
                          'python', '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe


TUPLE_TARGET = r"""def hit(log, a, b):
    log.append((a, b))
    return a == 1


def truthy(log, x):
    log.append(x)
    return x > 0


class Box:
    def __init__(self, pairs):
        self.pairs = pairs


def scan(rows):
    log = []
    print(any(hit(log, a, b) for a, b in rows))
    print(log)


def make():
    print("make")
    return [(0, 9), (1, 8), (2, 7)]


def main():
    scan([(0, 9), (1, 8), (2, 7)])
    log = []
    print(any(hit(log, a, b) for a, b in make()))
    print(log)
    box = Box([(0, 5), (3, 4)])
    log = []
    print(any(hit(log, a, b) for a, b in box.pairs))
    print(log)
    holder = {"rows": [(0, 1), (1, 2), (5, 6)]}
    log = []
    print(any(hit(log, a, b) for a, b in holder["rows"]))
    print(log)
    grids = [[(0, 1), (1, 2)], [(9, 9)]]
    log = []
    print(any(hit(log, a, b) for g in grids[0] for a, b in [g]))
    print(log)
    log = []
    print(all(truthy(log, x) for x in [1, 2, 0, 3]))
    print(log)
    log = []
    print(all(truthy(log, x) for x in [2, 4]))
    print(log)
    log = []
    print(any(truthy(log, x) for x in [0, 0]))
    print(log)
    log = []
    print(any(truthy(log, x) for x in []))
    print(log)
    log = []
    print(all(truthy(log, x) for x in []))
    print(log)
    log = []
    print(any(truthy(log, x) for x in [0, 3, 4]))
    print(log)
    log = []
    print(any(truthy(log, x) for x in range(-3, 4) if x != 0 and x > 0))
    print(log)


main()
"""

BOUNDARIES = r"""def mark(log, x):
    log.append(x)
    return x


def main():
    log = []
    print(any(mark(log, x) for x in (0, 1, 2)))
    print(log)
    log = []
    print(all(mark(log, x) for x in [1, 2, 0, 3]))
    print(log)
    log = []
    print(any(mark(log, x) for x in range(-2, 1)))
    print(log)
    log = []
    print(all(mark(log, x) for x in {"a": 1, "b": 2}))
    print(log)
    log = []
    print(any(mark(log, x) for x in "ab"))
    print(log)
    log = []
    print(any(mark(log, x) for x in []))
    print(log)
    log = []
    print(all(mark(log, x) for x in []))
    print(log)
    log = []
    print(any(mark(log, x) for x in [0, 1] if mark(log, 2)))
    print(log)
    log = []
    print(any(1 // x for x in [1, 0]))
    print(log)
    try:
        print(all(1 // x for x in [1, 0]))
    except ZeroDivisionError:
        print("zero")
    log = []
    print(all(mark(log, x) for x in [4, 5, 6] if x > 4))
    print(log)


main()
"""


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class Pre13Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, name + '_cpython.py')
            source.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=300)
            self.assertEqual(want.returncode, 0, want.stderr)
            for build, tag in ((build_general, 'g'), (build_default, 'd')):
                with self.subTest(build=tag):
                    res, exe = build(directory, text, name + '_' + tag)
                    self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                    got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                    self.assertEqual(got.stdout.decode('utf-8', 'replace'),
                                     want.stdout.decode('utf-8', 'replace'), tag)
                    self.assertEqual(got.returncode, want.returncode, (tag, got.stderr[-500:]))

    def test_tuple_destructuring_generator_stops_at_the_decisive_element(self):
        self.check('pre13_tuple_target', TUPLE_TARGET)

    def test_generator_boundaries(self):
        self.check('pre13_boundaries', BOUNDARIES)


if __name__ == '__main__':
    unittest.main()
