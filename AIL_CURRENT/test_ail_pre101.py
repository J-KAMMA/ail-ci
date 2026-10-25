"""pre101: `itertools.permutations(xs, None)` is the same as `permutations(xs)`.

CPython's signature spells the default as `r=None` and treats an actual None as "not
given", so the result is every full-length permutation.  The general path passed the
None through as r=0 and returned `[()]`.  The value may arrive as a constant, a keyword,
an argument, a list item, an attribute or a dict value; a value known only at run time
must be tested for None too.  The typed path already handles the literal None; it refuses
a None-typed variable by name (this language has no null value), so the default build
falls back to the general path there.

Both builds are compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')


PERM_NONE = r'''import itertools


def show(tag, fn):
    try:
        print(tag, list(fn()))
    except Exception as e:
        print(tag, type(e).__name__, e)


class Box:
    pass


xs = [1, 2, 3]
r = None
box = Box()
box.r = None
d = {"r": None}
items = [None, 2, "x"]


def pick(r):
    return itertools.permutations(xs, r)


show("no-r", lambda: itertools.permutations(xs))
show("literal", lambda: itertools.permutations(xs, None))
show("kw-literal", lambda: itertools.permutations(xs, r=None))
show("var", lambda: itertools.permutations(xs, r))
show("arg", lambda: pick(None))
show("list-item", lambda: itertools.permutations(xs, items[0]))
show("attr", lambda: itertools.permutations(xs, box.r))
show("dict", lambda: itertools.permutations(xs, d["r"]))
show("empty", lambda: itertools.permutations([], None))
show("one", lambda: itertools.permutations([7], None))
show("r0", lambda: itertools.permutations(xs, 0))
show("rn", lambda: itertools.permutations(xs, 3))
show("rgt", lambda: itertools.permutations(xs, 4))
show("r1", lambda: itertools.permutations(xs, 1))
'''

TYPED_NONE = r'''import itertools


def main():
    xs = [1, 2, 3]
    for a, b, c in itertools.permutations(xs, None):
        print(a, b, c)
    for a, b, c in itertools.permutations(xs):
        print(a, b, c)


main()
'''


class Pre101Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre101-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, src):
        path = self.dir / 'ref.py'
        path.write_text(src, encoding='utf-8')
        done = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, timeout=120)
        return done.stdout.replace(b'\r\n', b'\n'), done.returncode

    def build(self, src, name, general=False, typed_only=False):
        path = self.dir / (name + '.ail')
        path.write_text(src, encoding='utf-8')
        exe = self.dir / (name + '_' + ('g' if general else 't' if typed_only else 'd'))
        env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
        env.pop('AIL_UNIFIED_FORCE', None)
        env.pop('AIL_NO_GENERAL', None)
        if general:
            env['AIL_UNIFIED_FORCE'] = '1'
        if typed_only:
            env['AIL_NO_GENERAL'] = '1'
        done = subprocess.run([sys.executable, '-B', CLI, 'compile', path.name, '--syntax', 'python',
                               '-o', exe.name], cwd=self.dir, capture_output=True, text=True,
                              timeout=900, env=env)
        return done, exe

    def same(self, src, name):
        want, rc = self.cpython(src)
        for general in (False, True):
            done, exe = self.build(src, name, general=general)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, timeout=120)
            self.assertEqual(ran.stdout.replace(b'\r\n', b'\n'), want,
                             'general' if general else 'default')
            self.assertEqual(ran.returncode, rc, 'general' if general else 'default')
        return want

    def test_none_means_all_permutations(self):
        out = self.same(PERM_NONE, 'perm_none')
        full = b'[(1, 2, 3), (1, 3, 2), (2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1)]'
        for tag in (b'no-r', b'literal', b'kw-literal', b'var', b'arg', b'list-item', b'attr', b'dict'):
            self.assertIn(tag + b' ' + full + b'\n', out)
        self.assertIn(b'empty [()]\none [(7,)]\n', out)
        self.assertIn(b'r0 [()]\nrn [(1, 2, 3), (1, 3, 2), (2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1)]\n', out)
        self.assertIn(b'rgt []\nr1 [(1,), (2,), (3,)]\n', out)

    def test_typed_path_handles_literal_none(self):
        want, rc = self.cpython(TYPED_NONE)
        done, exe = self.build(TYPED_NONE, 'typed_none', typed_only=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, timeout=120)
        self.assertEqual(ran.stdout.replace(b'\r\n', b'\n'), want)
        self.assertEqual(ran.returncode, rc)


if __name__ == '__main__':
    unittest.main()
