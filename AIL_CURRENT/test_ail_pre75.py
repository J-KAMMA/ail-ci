"""pre75: itertools permutations / combinations / combinations_with_replacement with a negative r.

The general path returned [] where CPython raises
`ValueError: r must be non-negative`, and the default build's `list(...)` collection of
the same shape emitted invalid C.  A negative r, including a literal, now raises the
ValueError at run time on both builds.  The dynamic routes (argument, list item,
attribute, dict value) and the 0 / positive / r > n / omitted-r boundaries are compared
with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LITERAL = '''import itertools
try:
    list(itertools.%(func)s([1, 2], %(arg)s))
except ValueError as e:
    print(type(e).__name__, e)
'''

DYNAMIC_ROUTES = r'''import itertools


class Box:
    def __init__(self) -> None:
        self.r: int = -2


def run(seq: list[int], r: int, tag: str) -> None:
    try:
        n = 0
        for p in itertools.permutations(seq, r):
            n += len(p)
        print(tag, "perm", n)
    except ValueError as e:
        print(tag, "perm", type(e).__name__, e)
    try:
        n = 0
        for c in itertools.combinations(seq, r):
            n += len(c)
        print(tag, "comb", n)
    except ValueError as e:
        print(tag, "comb", type(e).__name__, e)
    try:
        n = 0
        for w in itertools.combinations_with_replacement(seq, r):
            n += len(w)
        print(tag, "cwr", n)
    except ValueError as e:
        print(tag, "cwr", type(e).__name__, e)


def main() -> None:
    run([1, 2, 3], -1, "argument")
    items = [-1]
    run([1, 2, 3], items[0], "listitem")
    b = Box()
    run([1, 2, 3], b.r, "attribute")
    d = {"r": -1}
    run([1, 2, 3], d["r"], "dictvalue")
    run([], -1, "empty-pool")


main()
'''

BOUNDARIES = r'''import itertools


def run(seq: list[int], r: int) -> None:
    p = c = w = 0
    for x in itertools.permutations(seq, r):
        p += len(x)
    for x in itertools.combinations(seq, r):
        c += len(x)
    for x in itertools.combinations_with_replacement(seq, r):
        w += len(x)
    print(r, p, c, w)


def main() -> None:
    for r in (0, 1, 2, 3, 5):
        run([1, 2, 3], r)
        run([], r)
    for x in itertools.permutations([]):
        print("none", len(x))
    for x in itertools.permutations([1, 2]):
        print("none", len(x))


main()
'''

CASES = [
    ('permutations', '-1'),
    ('permutations', 'r=-1'),
    ('combinations', '-1'),
    ('combinations_with_replacement', '-1'),
]


def _env(general):
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1', PYTHONUTF8='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return env


def _compile(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            src.name, '--syntax', 'python', '-o', exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=900,
                           env=_env(general))
    return built, exe


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return (done.returncode, done.stdout.replace(b'\r\n', b'\n')), done.stderr


class Pre75Tests(unittest.TestCase):
    def test_negative_literal_raises(self):
        for func, arg in CASES:
            text = LITERAL % {'func': func, 'arg': arg}
            slug = 'literal_%s_%s' % (func, 'kw' if arg.startswith('r=') else 'pos')
            self.check(slug, text)

    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre75-') as directory:
            want, cp_err = _cpython(directory, slug, text)
            self.assertEqual(want[0], 0, cp_err)
            for general in (True, False):
                built, exe = _compile(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertEqual(built.returncode, 0,
                                 '%s (general=%s)\n%s' % (slug, general,
                                                          built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                     cwd=directory)
                self.assertEqual((got.returncode, got.stdout.replace(b'\r\n', b'\n')), want,
                                 '%s (general=%s)\n%s' % (slug, general,
                                                          got.stderr.decode('utf-8', 'replace')))

    def test_dynamic_negative_routes_raise(self):
        self.check('dynamic_routes', DYNAMIC_ROUTES)

    def test_boundaries(self):
        self.check('boundaries', BOUNDARIES)


if __name__ == '__main__':
    unittest.main()
