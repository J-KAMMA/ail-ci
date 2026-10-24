"""pre116: a generator expression saved as a value is refused before it can abort.

The pre-existing difference recorded after job pre87: a generator expression whose body
raises was materialised eagerly on the general path.  CPython creates the generator object
and runs the body only at ``next()``, so a ``try`` around the consumption catches the error;
the eager lowering raised before the handler was live and the program exited 1 with empty
stdout.  The general path now refuses the construct by name, the same name the typed path
already uses, for a saved generator whose body can raise one of the catchable traps.

Immediate consumers (``sum``/``any``/``all``/``list``/``tuple``/``for``/``*``) and tuple
unpacking still use the existing eager lowering; the controls below keep matching CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REFUSAL = 'a generator expression used as a value'


LAZY_RAISING = r'''from enum import IntEnum


class Box:
    def __init__(self, v):
        self.v = v


class Z(IntEnum):
    ZERO = 0


def helper(a, b):
    return a % b


def floor_helper(a, b):
    return a // b


def consume(g):
    return next(g)


def main():
    g = (helper(5, 0) for _ in range(1))
    try:
        print(next(g))
    except ZeroDivisionError as e:
        print("assign", str(e))
    h = (helper(5, 0) for _ in range(1))
    try:
        print(consume(h))
    except ZeroDivisionError as e:
        print("argument", str(e))
    items = [(helper(5, 0) for _ in range(1))]
    try:
        print(next(items[0]))
    except ZeroDivisionError as e:
        print("list-item", str(e))
    box = Box((helper(5, 0) for _ in range(1)))
    try:
        print(next(box.v))
    except ZeroDivisionError as e:
        print("attribute", str(e))
    d = {"g": (helper(5, 0) for _ in range(1))}
    try:
        print(next(d["g"]))
    except ZeroDivisionError as e:
        print("dict-value", str(e))
    print("after")


main()
'''

LAZY_RAISING_EDGES = r'''from enum import IntEnum


class Z(IntEnum):
    ZERO = 0


def helper(a, b):
    return a % b


def gen():
    return (helper(-7, 0) for _ in range(1))


def gen_floor():
    return (helper(5, 0) // 1 for _ in range(1))


def gen_bool():
    return (helper(5, False) for _ in range(1))


def gen_enum():
    return (helper(5, Z.ZERO) for _ in range(1))


def gen_empty():
    return (helper(5, 0) for _ in [])


def main():
    for make in (gen, gen_floor, gen_bool, gen_enum, gen_empty):
        try:
            print(next(make()))
        except ZeroDivisionError as e:
            print("caught", str(e))
    print("after")


main()
'''

CONSUMED_CONTROL = r'''def body(x):
    return x * 10


def main():
    print(sum(body(x) for x in [1, 2, 3]))
    print(list(body(x) for x in [1, 2, 3]))
    print(tuple(body(x) for x in [1, 2]))
    print(sorted(body(x) for x in [3, 1, 2]))
    print(any(x > 2 for x in [1, 2, 3]))
    print(all(x < 5 for x in [1, 2, 3]))
    for v in (body(x) for x in [1, 2]):
        print("for", v)
    print(*(body(x) for x in [4, 5]))
    a, b = (int(part) for part in "10,20".split(","))
    print(a, b)
    print(" ".join(str(x) for x in [1, 2, 3]))
    print("after")


main()
'''

RETURN_SAFE = r'''def long_words(text):
    return ((position, word) for position, word in enumerate(text.split()) if len(word) > 4)


def main():
    for position, word in long_words("The quick brown fox jumps over the lazy dog"):
        print(position, word)
    print("after")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return (done.stdout.replace(b'\r\n', b'\n'), done.returncode), done.stderr.decode('utf-8', 'replace')


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env), exe


class Pre116Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre116-') as directory:
            for general in (True, False):
                built, _ = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, '%s (general=%s)\n%s' % (slug, general, output))
                self.assertIn(REFUSAL, output, '%s (general=%s)\n%s' % (slug, general, output))
                self.assertNotIn('Traceback', built.stderr, '%s (general=%s)\n%s' % (slug, general, output))

    def same(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre116-') as directory:
            (want, want_rc), err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                built, exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 0, '%s (general=%s)\n%s' % (slug, general, output))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), (want, want_rc),
                                 '%s (general=%s)\n%s' % (slug, general, got.stderr.decode('utf-8', 'replace')[-2000:]))

    def test_lazy_raising_is_refused(self):
        self.refused('lazy_raising', LAZY_RAISING)

    def test_lazy_raising_edges(self):
        self.refused('lazy_raising_edges', LAZY_RAISING_EDGES)

    def test_consumed_in_place_matches(self):
        self.same('consumed_control', CONSUMED_CONTROL)

    def test_safe_returned_generator_matches(self):
        self.same('return_safe', RETURN_SAFE)


if __name__ == '__main__':
    unittest.main()
