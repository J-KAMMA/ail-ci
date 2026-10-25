"""pre233: enumerate()'s start is converted as CPython's PyNumber_Index does.

A pre-existing difference (recorded as ``C?-job-fuzz8-10220554-2``): the general path read the
start straight out of the value union, so ``enumerate("ab", None)`` printed ``[(0, 'a'), (1, 'b')]``
and a float, str or list start became a pointer-sized integer, where CPython raises
``TypeError: '<type>' object cannot be interpreted as an integer`` at call time.  The general
emitter now passes the object to the runtime builtin, which converts an int or bool and raises
CPython's TypeError for every other type before the iterable is opened.

The cases below cover the start as a literal, an argument, a list item, an attribute and a dict
value; positional and ``start=`` forms; the None, float, str, bytes, list, tuple, dict and set
types; bool, negative and int64-boundary values; an empty iterable; for loops and comprehensions;
argument-evaluation order; and the error chosen when the iterable and the start are both invalid.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

ENUM_TYPES = r'''class Box:
    def __init__(self, v):
        self.v = v


def show(start):
    try:
        print(list(enumerate("ab", start)))
    except Exception as e:
        print(type(e).__name__, str(e))


def show_kw(start):
    try:
        print(list(enumerate("ab", start=start)))
    except Exception as e:
        print(type(e).__name__, str(e))


def show_src():
    items = [None, "x", 2.5]
    for v in items:
        show(v)
    d = {"s": None, "n": 4}
    show(d["s"])
    show(d["n"])
    b = Box("q")
    show(b.v)
    show(b)
    show([1])
    show((1,))
    show(b"x")
    show({"a": 1})
    show({1, 2})
    show(1.5)
    try:
        print(list(enumerate("ab", 1.5)))
    except Exception as e:
        print(type(e).__name__, str(e))


def show_ok(xs, start):
    try:
        print(list(enumerate(xs, start)))
    except Exception as e:
        print(type(e).__name__, str(e))


def main():
    for v in (None, 1.5, "x", [1], (1,), b"x", {"a": 1}, {1, 2}):
        show(v)
        show_kw(v)
    for v in (True, False, 0, -3, 7, 9223372036854775806):
        show(v)
        show_kw(v)
    show_src()
    show_ok("", None)
    show_ok("", 5)
    show_ok([10, 20], 0)
    show_ok([10, 20], -5)
    show_ok([10, 20], True)
    show_ok([10, 20], 9223372036854775806)
    show_ok(range(3), -9223372036854775807)
    show_ok({"a": 1, "b": 2}, 1)
    print(list(enumerate("ab")))


main()
'''

ENUM_LOOP = r'''def mark(tag):
    print("eval", tag)
    return tag


def loop(start):
    for i, ch in enumerate("ab", start):
        print(i, ch)


def comp(start):
    return [(i, ch) for i, ch in enumerate("ab", start)]


def show(start):
    for f in (loop, comp):
        try:
            r = f(start)
            if r is not None:
                print(r)
        except Exception as e:
            print(type(e).__name__, str(e))


def both(it, start):
    try:
        print(list(enumerate(it, start)))
    except Exception as e:
        print(type(e).__name__, str(e))


def order(start):
    try:
        it = enumerate(mark("iterable"), start)
        print("made ok")
        print(list(it))
    except Exception as e:
        print(type(e).__name__, str(e))


def main():
    for v in (None, 1.5, "x", [1], True, -2, 0):
        show(v)
    both(5, None)
    both(None, 1.5)
    both(5, 2)
    both([], None)
    order(2.5)
    order(None)
    order(3)


main()
'''


def _run(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.stdout + built.stderr
    done = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True, timeout=120)
    return done, ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], cwd=directory,
                          capture_output=True, text=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))


class Pre233Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre233-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _check(self, name, text):
        want = _cpython(self.dir, name, text)
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in (False, True):
            got, err = _run(self.dir, name + ('_g' if general else '_d'), text, general)
            self.assertIsNotNone(got, err)
            self.assertEqual((got.returncode, got.stdout), (0, want.stdout),
                             'general=%s\n%s' % (general, got.stderr))

    def test_start_types_match_cpython(self):
        self._check('types', ENUM_TYPES)

    def test_start_in_loops_and_error_order(self):
        self._check('loop', ENUM_LOOP)


if __name__ == '__main__':
    unittest.main()
