"""Saved generator expressions (the stdlib reach census's most common first refusal).

A generator expression used as a value was refused by both builds.  The general path now lowers
it to a real module-level generator function, so the body runs lazily (outer iterable at the call,
element and exception at next()), and the default build routes such a program there.  Every case
below is compared with CPython 3.12 on the default and the forced-general build.  A generator
inside a class body, a nested generator expression, a walrus inside one, a captured local that is
rebound after creation (on the same line, in a later loop iteration, through a nested function's
`nonlocal` write, or by a later store), a captured local that may be unbound, and a constructor of
a class defined by the program keep the by-name refusal.  A generator in a default argument or
annotation reads the enclosing scope (a parameter of the `def` does not shadow it), and the
module-global read is left for consumption time.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
REFUSAL = 'generator expression'

VALUES = r'''def consume(g):
    return [x + 1 for x in g]


class Box:
    def __init__(self, value):
        self.value = value


def make(lo, hi):
    return (x * x for x in range(lo, hi))


def main():
    g = (x * 2 for x in [-2, -1, 0, 1, 2])
    print("made")
    print(next(g))
    print(list(g))
    print(list(g))
    print(list(x for x in []))
    print(consume(x + 3 for x in [1, 2, 3]))
    items = [(str(x) for x in [4, 5])]
    print(list(items[0]))
    box = Box((x - 1 for x in [7, 8]))
    print(list(box.value))
    d = {"g": (x / 2 for x in [10, 12])}
    print(list(d["g"]))
    a = make(2, 5)
    b = a
    print(next(a), next(b), list(a))
    print(list((i * 10 + j for i in [1, 2] for j in [3, 4] if i != 2 or j != 3)))
    print(" ".join(str(x) for x in [1, 2, 3]))
main()
'''

LAZY = r'''def bad(x):
    if x == 2:
        raise ValueError("two")
    return x


def source():
    print("source called")
    for x in [1, 2]:
        print("source yields", x)
        yield x


def main():
    g = (bad(x) for x in [1, 2, 3])
    print("before")
    try:
        print(next(g))
        print(next(g))
    except ValueError as e:
        print("caught", str(e))
    h = (10 // x for x in source())
    print("made h")
    print(next(h))
    print(next(h))
    try:
        print(next(h))
    except StopIteration:
        print("stop")
main()
'''

MUTATION = r'''def gen(items):
    return (x for x in items)


def main():
    xs = [1, 2, 3]
    g = (100 // x for x in xs)
    xs.append(4)
    print(list(g))
    ys = [1, 2]
    h = (ys[0] * x for x in [1, 2])
    ys[0] = 7
    print(list(h))
    print(list(gen([5, 6])))
main()
'''

REBOUND = r'''def main():
    factor = 2
    g = (x * factor for x in [1, 2])
    factor = 5
    print(list(g))
main()
'''

NESTED = r'''def main():
    g = ((y for y in [1, 2]) for x in [1])
    print(list(g))
main()
'''

SAME_LINE = r'''def main():
    x = 1; g = (10 // x for _ in [0]); x = 2; print(list(g))
main()
'''

NONLOCAL = r'''def main():
    x = 1
    def bump():
        nonlocal x
        x = 2
    g = (10 // x for _ in [0])
    bump()
    print(list(g))
main()
'''

UNBOUND = r'''def main():
    if False:
        x = 3
    g = (10 // x for _ in [0])
    print("made")
    try:
        print(list(g))
    except UnboundLocalError:
        print("unbound")
main()
'''

DELETED_BEFORE = r'''def main():
    x = 1
    del x
    g = (10 // x for _ in [0])
    print("made")
    try:
        print(list(g))
    except NameError:
        print("nameerror")
main()
'''

EXCEPT_NAME = r'''def main():
    try:
        raise ValueError(3)
    except ValueError as x:
        g = (10 // x for _ in [0])
    print("made")
    try:
        print(list(g))
    except NameError:
        print("nameerror")
main()
'''

SAME_LINE_BEFORE = r'''def main():
    x = 1; g = (10 // x for _ in [0]); print(list(g))
main()
'''

PARAM_CAPTURE = r'''def make(x):
    return (10 // x for _ in [0])


def main():
    print(list(make(2)))
    print(list(make(-3)))
main()
'''

NESTED_READ = r'''def main():
    x = 2
    def reader():
        return list((10 // x for _ in [0]))
    print(reader())
main()
'''

LOOP_AFTER = r'''def main():
    gens = []
    for x in [1, 2, 3]:
        gens.append((10 // x for _ in [0]))
    print([list(g) for g in gens])
main()
'''

WHILE_AFTER = r'''def main():
    gens = []
    i = 0
    while i < 2:
        x = i + 1
        gens.append((10 // x for _ in [0]))
        i = i + 1
    print([list(g) for g in gens])
main()
'''

LOOP_TWO_TARGETS = r'''def main():
    gens = []
    for x, y in [(1, 2), (3, 4)]:
        gens.append((10 // (x + y) for _ in [0]))
    print([list(g) for g in gens])
main()
'''

NESTED_LOOP = r'''def main():
    gens = []
    for i in [1, 2]:
        x = i + 1
        for j in [0]:
            gens.append((10 // x for _ in [0]))
    print([list(g) for g in gens])
main()
'''

LOOP_BEFORE = r'''def main():
    x = 2
    gens = []
    for i in [1, 2]:
        gens.append((10 // x for _ in [0]))
    print([list(g) for g in gens])
main()
'''

DEFAULT_STALE = r'''def main():
    x = 100
    def f(x=1, g=(10 // x for _ in [0])):
        return list(g)
    x = 7
    return f()
print(main())
'''

DEFAULT_PARAM = r'''def make(x):
    def f(x=1, g=(10 // x for _ in [0])):
        return list(g)
    return f()
print(make(2))
print(make(-3))
'''

DEFAULT_SAFE = r'''def main():
    x = 5
    def f(x=1, g=(10 // x for _ in [0])):
        return list(g)
    return f()
print(main())
'''

DEFAULT_GLOBAL_REBOUND = r'''x = 100
def main():
    def f(x=1, g=(10 // x for _ in [0])):
        return list(g)
    global x
    x = 7
    return f()
print(main())
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(CLI), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class StdlibReachTests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-stdlib-reach-') as directory:
            want = _cpython(directory, slug, text)
            for general in (True, False):
                tag = 'g' if general else 'd'
                built, exe = _build(directory, '%s_%s' % (slug, tag), text, general)
                self.assertEqual(built.returncode, 0, '%s (%s)\n%s' % (slug, tag, built.stderr[-2000:]))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), want,
                                 '%s (%s)\n%s' % (slug, tag, got.stderr.decode('utf-8', 'replace')[-2000:]))

    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-stdlib-reach-') as directory:
            for general in (True, False):
                tag = 'g' if general else 'd'
                built, _ = _build(directory, '%s_%s' % (slug, tag), text, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, '%s (%s) built\n%s' % (slug, tag, output))
                self.assertIn(REFUSAL, output, '%s (%s)\n%s' % (slug, tag, output[-2000:]))

    def test_saved_generator_values_match(self):
        self.check('values', VALUES)

    def test_lazy_body_and_outer_iterable_match(self):
        self.check('lazy', LAZY)

    def test_captured_container_mutation_matches(self):
        self.check('mutation', MUTATION)

    def test_rebound_capture_and_nested_generator_refused(self):
        self.refused('rebound', REBOUND)
        self.refused('nested', NESTED)

    def test_same_line_rebound_capture_refused(self):
        self.refused('same_line', SAME_LINE)

    def test_nonlocal_rebound_capture_refused(self):
        self.refused('nonlocal', NONLOCAL)

    def test_possibly_unbound_capture_refused(self):
        self.refused('unbound', UNBOUND)
        self.refused('deleted_before', DELETED_BEFORE)
        self.refused('except_name', EXCEPT_NAME)

    def test_stable_captures_match(self):
        self.check('same_line_before', SAME_LINE_BEFORE)
        self.check('param_capture', PARAM_CAPTURE)
        self.check('nested_read', NESTED_READ)

    def test_loop_rebound_capture_refused(self):
        self.refused('loop_after', LOOP_AFTER)
        self.refused('while_after', WHILE_AFTER)
        self.refused('loop_two_targets', LOOP_TWO_TARGETS)
        self.refused('nested_loop', NESTED_LOOP)

    def test_loop_before_capture_matches(self):
        self.check('loop_before', LOOP_BEFORE)

    def test_default_argument_scope(self):
        self.refused('default_stale', DEFAULT_STALE)
        self.check('default_param', DEFAULT_PARAM)
        self.check('default_safe', DEFAULT_SAFE)
        self.check('default_global_rebound', DEFAULT_GLOBAL_REBOUND)


if __name__ == '__main__':
    unittest.main()
