"""obs4 (`ail build --cpython`): read-only methods of plain classes.

A method whose `self` is only read (`self.<field>` of a scalar or int/float list kind, and calls
of other such methods) is compiled as a synthetic top-level function that takes the fields as
parameters.  The C entry installed on the method's function checks, before any native work, that
`type(self)` is exactly the class, that the class has no metaclass and the generic getattr, that
no class attribute anywhere in the MRO is named like a field, and that every method the body calls
on `self` is still the installed def and is not shadowed on the instance; then it reads the fields
and checks them like arguments.  Anything else runs the original method.  Every runner's output
must equal CPython's byte for byte.
"""
import ast
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
HAVE_HEADERS = (Path(sysconfig.get_paths().get('include', '/nonexistent')) / 'Python.h').is_file()
VECTORCALL = sys.version_info >= (3, 12)

import ail_cpython_hybrid as hybrid  # noqa: E402

METHODS = '''
class Tree:
    def __init__(self) -> None:
        self.keys = []
        self.left = []
        self.right = []
        self.size = 0
        self.scale = 1.5
        self.name = "t"

    def insert(self, key: int) -> None:
        self.keys.append(key)
        self.left.append(-1)
        self.right.append(-1)
        idx = self.size
        self.size += 1
        if idx == 0:
            return
        cur = 0
        while True:
            if key < self.keys[cur]:
                nxt = self.left[cur]
                if nxt < 0:
                    self.left[cur] = idx
                    return
                cur = nxt
            else:
                nxt = self.right[cur]
                if nxt < 0:
                    self.right[cur] = idx
                    return
                cur = nxt

    def height(self) -> int:
        return self._height(0)

    def _height(self, idx: int) -> int:
        if idx < 0:
            return 0
        a = self._height(self.left[idx])
        b = self._height(self.right[idx])
        if a > b:
            return a + 1
        return b + 1

    def total(self) -> int:
        acc = 0
        for k in self.keys:
            acc += k
        return acc

    def scaled(self, x: float) -> float:
        return x * self.scale

    def label_len(self) -> int:
        return len(self.name)

    def key_at(self, i: int) -> int:
        return self.keys[i]


class Point:
    z = 0

    def __init__(self, x: int) -> None:
        self.x = x

    def get(self) -> int:
        return self.x
'''

RUNNER = '''
import sys
import methods as m


def show(label, f, *args):
    try:
        r = f(*args)
        print(label, type(r).__name__, repr(r))
    except Exception as e:
        print(label, 'raised', type(e).__name__)


t = m.Tree()
for k in [5, 3, 8, 1, 4, 7, 9, 2, 6]:
    t.insert(k)
show('height', t.height)
show('total', t.total)
show('scaled', t.scaled, 2.0)
show('scaled_int_arg', t.scaled, 2)
show('label', t.label_len)
show('key_at', t.key_at, 2)
show('key_at_neg', t.key_at, -1)
show('key_at_oob', t.key_at, 99)
t.scale = 2
show('scaled_int_field', t.scaled, 2.0)
t.scale = 1.5
t.keys.append(2 ** 70)
show('total_big', t.total)
t.keys.pop()
t.keys.append(True)
show('total_bool', t.total)
t.keys.pop()
t.keys.append(2 ** 62)
t.keys.append(2 ** 62)
show('total_overflow', t.total)
t.keys.pop()
t.keys.pop()
t._height = lambda idx: 100
show('height_shadowed', t.height)
del t._height
show('height_unshadowed', t.height)
orig = m.Tree._height
m.Tree._height = lambda self, idx: -1
show('height_patched', t.height)
m.Tree._height = orig
show('height_restored', t.height)


def other(self, idx):
    return 42


code = orig.__code__
orig.__code__ = other.__code__
show('height_code', t.height)
orig.__code__ = code
show('height_code_restored', t.height)


class Sub(m.Tree):
    def _height(self, idx):
        return 7


class Plain(m.Tree):
    pass


s = Sub()
s.insert(1)
show('sub_height', s.height)
p = Plain()
p.insert(1)
p.insert(2)
show('plain_height', p.height)
m.Tree.name = property(lambda self: 'property!')
show('label_property', t.label_len)
del m.Tree.name
show('label_restored', t.label_len)
t2 = m.Tree()
del t2.name
show('label_missing', t2.label_len)
m.Tree.name = 'classattr'
show('label_classattr', t2.label_len)
del m.Tree.name


class Other:
    def __init__(self):
        self.keys = [1, 2]


o = Other()
show('unbound_other', m.Tree.total, o)
o.__class__ = m.Tree
show('reassigned_class', o.total)
deep = m.Tree()
for k in range(150):
    deep.insert(k)
sys.setrecursionlimit(120)
show('deep_height_limit', deep.height)
sys.setrecursionlimit(1000)
show('deep_height', deep.height)
for _ in range(2000):
    t.height()
    t.total()
print('loops-ok')
show('point', m.Point(3).get)
'''

NATIVE = ('Tree.height', 'Tree._height', 'Tree.total', 'Tree.scaled', 'Tree.label_len')
# key_at: loop-free with a list field (the entry copy would cost more than the body)
REFUSED = ('Tree.insert', 'Tree.__init__', 'Point.get', 'Tree.key_at')


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=600)


class Synthetics(unittest.TestCase):
    """The desugaring and the field-kind guess, on plain ASTs (no compiler needed)."""

    def test_fields_become_parameters(self):
        synth, refusals = hybrid._method_synthetics(ast.parse(METHODS))
        by = {meta['attr']: (fn, meta) for fn, meta in synth}
        self.assertEqual(sorted(by), ['_height', 'height', 'label_len', 'scaled', 'total'])
        self.assertIn('loop-free', refusals['Tree.key_at'])
        fn, meta = by['height']
        self.assertEqual(meta['fields'], [('left', 'list[int]'), ('right', 'list[int]')])
        self.assertEqual(meta['nown'], 0)
        self.assertIn('%s(__ail_f_left, __ail_f_right, 0)'
                      % hybrid._synthetic_name('Tree', '_height'), ast.unparse(fn))
        self.assertEqual(by['scaled'][1]['fields'], [('scale', 'float')])
        self.assertEqual(by['label_len'][1]['fields'], [('name', 'str')])
        self.assertIn('stored', refusals['Tree.insert'])
        self.assertIn('class attributes', refusals['Point.get'])

    def test_refusals(self):
        cases = {
            # self escapes
            'def f(self) -> int:\n        return g(self)\n': 'self is stored',
            # a field store
            'def f(self) -> int:\n        self.n = 1\n        return 1\n': 'self is stored',
            # a field of unknown kind
            'def f(self) -> int:\n        return self.d\n': 'no scalar',
            # a closure over self
            'def f(self) -> int:\n        h = lambda: self.n\n        return self.n\n':
                'nested scope',
        }
        for body, why in cases.items():
            src = ('class C:\n    def __init__(self, n: int) -> None:\n        self.n = n\n'
                   '        self.d = {}\n\n    ' + body)
            synth, refusals = hybrid._method_synthetics(ast.parse(src))
            self.assertEqual([m['attr'] for _f, m in synth], [], body)
            self.assertIn(why, refusals['C.f'], body)
        self.assertEqual(hybrid._synthetic_name('A_', 'b'),
                         '__ail_m2_A__b')
        self.assertNotEqual(hybrid._synthetic_name('A_', 'b'), hybrid._synthetic_name('A', '_b'))


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class Runs(unittest.TestCase):

    def test_methods_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-methods-') as tmp:
            src = Path(tmp) / 'methods.py'
            src.write_text(METHODS, encoding='utf-8')
            out = Path(tmp) / 'out'
            built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)],
                        tmp, env=dict(os.environ, AIL_NO_CACHE='1'))
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
            for name in NATIVE:
                self.assertIn(name, report['accelerated'], report['rejected'].get(name))
            for name in REFUSED:
                self.assertNotIn(name, report['accelerated'])
                self.assertIn(name, report['rejected'])
            runner = Path(tmp) / 'runner.py'
            runner.write_text(RUNNER, encoding='utf-8')
            want = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=tmp))
            got = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(got.stdout.decode(), want.stdout.decode(), got.stderr[-2000:])
            self.assertEqual(got.returncode, want.returncode)
            self.assertIn(b'loops-ok', got.stdout)
            self.assertIn(b'deep_height_limit raised RecursionError', got.stdout)
            if VECTORCALL:
                probe = ('import methods as m\nnat = m._ail_hybrid_native\n'
                         'print([nat._ail_is_native(getattr(getattr(m, c), a)) for c, a in '
                         '[n.split(".") for n in %r]])\n' % (NATIVE,))
                got = run([sys.executable, '-B', '-c', probe], str(out),
                          env=dict(os.environ, PYTHONPATH=str(out)))
                self.assertEqual(got.stdout.strip(), repr([True] * len(NATIVE)).encode(),
                                 got.stderr[-2000:])


if __name__ == '__main__':
    unittest.main()
