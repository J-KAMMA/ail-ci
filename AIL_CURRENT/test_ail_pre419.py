"""pre419: subscripting a class object names the class, as CPython does.

The pre396 review recorded as pre-existing that ``A[0]`` on ``class A`` raised
``TypeError: 'type' object is not subscriptable`` on both builds, while CPython 3.12 says
``TypeError: type 'A' is not subscriptable``.  The general runtime now quotes the class's
own name for both an index and a slice key, capped like CPython at 200 characters.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class Pre419Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre419-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_class_subscript_names_the_class(self):
        self.check('keys_and_slices', '''
class A:
    pass


class B(A):
    pass


for k in [None, True, False, 0, -1, 1.5, 'x', (1, 2), [1, 2], b'x']:
    try:
        print(A[k])
    except Exception as e:
        print(type(e).__name__, e)
for sl in [slice(None), slice(1, 2), slice(None, None, -1), slice(0, 10, 2)]:
    try:
        print(A[sl])
    except Exception as e:
        print(type(e).__name__, e)
for label, obj in [('A', A), ('B', B)]:
    try:
        print(obj[1:2])
    except Exception as e:
        print(label, type(e).__name__, e)
''')

    def test_routes_to_a_class_value(self):
        self.check('routes', '''
class A:
    pass


class B(A):
    pass


class Holder:
    pass


def sub(x, k):
    return x[k]


def pick():
    return B


holder = Holder()
holder.k = B
items = [A, B]
mapping = {'a': A, 'b': B}
alias = B
for label, fn in [('direct', lambda: A[0]), ('alias', lambda: alias[0]),
                  ('arg', lambda: sub(A, 0)), ('item', lambda: items[1][0]),
                  ('dict', lambda: mapping['b'][0]), ('attr', lambda: holder.k[0]),
                  ('return', lambda: pick()[0]), ('slice', lambda: sub(B, slice(1, 2)))]:
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, e)
''')

    def test_long_class_name_is_capped_like_cpython(self):
        for length in (199, 200, 201, 250):
            name = 'K' * length
            text = ('class %s:\n    pass\n'
                    'try:\n    %s[0]\nexcept Exception as e:\n'
                    '    s = str(e)\n'
                    '    print(%d, type(e).__name__, len(s), s[:10], s[-24:])\n'
                    % (name, name, length))
            self.check('long_%d' % length, text)

    def test_non_class_subscript_unchanged(self):
        self.check('control', '''
class A:
    pass

a = A()
a.x = 5
print(type(a).__name__, a.x, A.__name__, isinstance(a, A))
try:
    a[0]
except Exception as e:
    print(type(e).__name__, e)
try:
    print(a[0:2])
except Exception as e:
    print(type(e).__name__, e)
for o in [None, True, 1, 1.5, 'x', [1], (1,), {1: 2}]:
    try:
        print(o[0])
    except Exception as e:
        print(type(e).__name__, e)
''')


if __name__ == '__main__':
    unittest.main()
