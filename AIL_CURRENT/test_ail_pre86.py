"""pre86: itertools.permutations treats r=None as if r were left out.

`permutations(xs, None)` yielded only `()` on both builds; CPython's default
argument is None, so an explicit None means r=len(pool) and the full
permutations are produced.  The general path lowered the boxed value with
`(r).i`, so a None (or a value reaching the call through an argument, a list
item, an attribute or a dict value) became r=0.  The run-time helper now tests
the tag at run time: None keeps the pool size, an int or bool is the requested
r, and anything else raises CPython 3.12's TypeError.

Each program is built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PERM_NONE = r'''from itertools import permutations


def main():
    print(list(permutations([1, 2, 3], None)))
    print(list(permutations("ab", None)))
    print(list(permutations([], None)))
    print(list(permutations([1, 2], r=None)))
    print(list(permutations([1], None)), list(permutations([], 0)))


main()
'''

PERM_NONE_ROUTES = r'''from itertools import permutations


class Box:
    def __init__(self, value):
        self.r = value


def get_none():
    return None


def via_arg(n, xs):
    return list(permutations(xs, n))


def main():
    xs = [1, 2, 3]
    n = None
    print("arg", via_arg(n, xs))
    print("call", list(permutations(xs, get_none())))
    print("item", list(permutations(xs, [None][0])))
    box = Box(None)
    print("attr", list(permutations(xs, box.r)))
    d = {"r": None}
    print("dict", list(permutations(xs, d["r"])))
    print("keyword", list(permutations(xs, r=n)))
    print("twice", list(permutations(xs, n)), list(permutations(xs, n)))


main()
'''

PERM_NONE_BOUNDS = r'''from itertools import permutations


def main():
    pools = ([], [1], [1, 2])
    for xs in pools:
        for k in (None, 0, 1, 2, 3):
            n = 0
            for p in permutations(xs, k):
                n += 1
            print(len(xs), k, n)


main()
'''

PERM_NONE_TYPED = r'''from itertools import permutations


def count(xs, k):
    n = 0
    for p in permutations(xs, k):
        n += 1
    return n


def main():
    xs = [1, 2, 3]
    print(count(xs, None))
    print(count(xs, 1))
    print(count(xs, 2))


main()
'''

PERM_NONE_TYPES = r'''from itertools import permutations


def main():
    for r in (True, False):
        print(r, list(permutations([1, 2], r)))
    for bad in (1.5, "2", [2]):
        try:
            print(list(permutations([1, 2], bad)))
        except TypeError as e:
            print("TypeError", e)


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


class Pre86Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre86-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_permutations_none(self):
        self.check('perm_none', PERM_NONE)

    def test_permutations_none_routes(self):
        self.check('perm_none_routes', PERM_NONE_ROUTES)

    def test_permutations_none_bounds(self):
        self.check('perm_none_bounds', PERM_NONE_BOUNDS)

    def test_permutations_none_typed(self):
        self.check('perm_none_typed', PERM_NONE_TYPED)

    def test_permutations_none_types(self):
        self.check('perm_none_types', PERM_NONE_TYPES)


if __name__ == '__main__':
    unittest.main()
