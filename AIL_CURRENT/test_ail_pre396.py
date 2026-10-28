"""Pre396: item deletion unsupported wording matches CPython.

The pre377 review recorded as pre-existing that ``del`` of an item from None, bool, int,
float, a builtin function, a lambda, a str keyed by a tuple, or a class said ``doesn't``
where CPython 3.12 says ``does not``.  CPython uses the ``doesn't`` form only on
``PySequence_DelItem``'s index-conversion path, which a sequence-like receiver (str, tuple,
range, set, frozenset, a bytes value, a user instance) takes for an int/bool key; every
other key uses ``PyObject_DelItem``'s ``does not``.  Both builds now pick the wording from
the receiver kind and key, and name a builtin function / user instance as CPython does.
List/dict deletion and a user ``__delitem__`` are unchanged; a class subscription (a
different, untouched pre-existing item) is not covered here.
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
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def last_line(data):
    lines = [line for line in data.decode('utf-8', 'replace').splitlines() if line.strip()]
    return lines[-1] if lines else ''


class Pre396Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre396-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))
                self.assertEqual(last_line(got.stderr), last_line(want.stderr),
                                 (name, general, got.stderr[-800:]))

    def test_does_not_wording(self):
        self.check('implementations', '''
try:
    del None[0]
except Exception as e:
    print(type(e).__name__, e)
try:
    del True[0]
except Exception as e:
    print(type(e).__name__, e)
try:
    del (1)[0]
except Exception as e:
    print(type(e).__name__, e)
try:
    del (1.0)[0]
except Exception as e:
    print(type(e).__name__, e)
try:
    del len[0]
except Exception as e:
    print(type(e).__name__, e)
try:
    del (lambda: 1)[0]
except Exception as e:
    print(type(e).__name__, e)
try:
    del "ab"[(1, 2)]
except Exception as e:
    print(type(e).__name__, e)
class A:
    pass
try:
    del A[0]
except Exception as e:
    print(type(e).__name__, e)
''')

    def test_index_path_keeps_doesnt(self):
        self.check('index_paths', '''
for o in ["ab", (1, 2), range(2), {1}, frozenset([1]), b"ab"]:
    try:
        del o[0]
    except Exception as e:
        print(type(e).__name__, e)
    try:
        del o[True]
    except Exception as e:
        print(type(e).__name__, e)
class C:
    pass
try:
    del C()[0]
except Exception as e:
    print(type(e).__name__, e)
try:
    del C()[True]
except Exception as e:
    print(type(e).__name__, e)
''')

    def test_non_index_keys(self):
        self.check('non_index_keys', '''
for o in ["ab", (1, 2), len, lambda: 1, 3]:
    try:
        del o[(1, 2)]
    except Exception as e:
        print(type(e).__name__, e)
class C:
    pass
try:
    del C()[(1, 2)]
except Exception as e:
    print(type(e).__name__, e)
try:
    del C()[1:2]
except Exception as e:
    print(type(e).__name__, e)
try:
    del "ab"[1:2]
except Exception as e:
    print(type(e).__name__, e)
try:
    del len[1:2]
except Exception as e:
    print(type(e).__name__, e)
try:
    del C[1:2]
except Exception as e:
    print(type(e).__name__, e)
''')

    def test_empty_and_negative(self):
        self.check('empty_negative', '''
for o in ["", (), range(0), set(), frozenset()]:
    try:
        del o[0]
    except Exception as e:
        print(type(e).__name__, e)
for o in ["ab", (1, 2), range(2)]:
    try:
        del o[-1]
    except Exception as e:
        print(type(e).__name__, e)
    try:
        del o[-99]
    except Exception as e:
        print(type(e).__name__, e)
''')

    def test_routes_and_alias(self):
        self.check('routes', '''
class Box:
    pass


def drop(x, k):
    try:
        del x[k]
    except Exception as e:
        print(type(e).__name__, e)


box = Box()
box.v = None
holder = {"none": None, "int": 7, "bif": len}
items = [None, True, 2, 2.5, lambda: 3, "xy", (4, 5), Box]
for o in items:
    drop(o, 0)
drop(box.v, 0)
drop(holder["none"], 0)
drop(items[0], 0)
drop(holder["int"], 0)
drop(holder["bif"], 0)
drop(items[4], 0)
try:
    del box.v[0]
except Exception as e:
    print(type(e).__name__, e)
try:
    del holder["none"][0]
except Exception as e:
    print(type(e).__name__, e)
a = None
b = a
try:
    del b[0]
except Exception as e:
    print(type(e).__name__, e)
c = 5
d = c
try:
    del d[0]
except Exception as e:
    print(type(e).__name__, e)
e = len
f = e
try:
    del f[0]
except Exception as e:
    print(type(e).__name__, e)
g = "ab"
h = g
try:
    del h[(1, 2)]
except Exception as e:
    print(type(e).__name__, e)
''')

    def test_deletion_still_works(self):
        self.check('deletion_works', '''
xs = [1, 2, 3]
del xs[0]
print(xs)
d = {"a": 1, "b": 2}
del d["a"]
print(d)
class C:
    def __init__(self):
        self.v = 9
    def __delitem__(self, k):
        self.v = self.v + k
c = C()
del c[3]
print(c.v)
''')

    def test_uncaught_messages(self):
        self.check('uncaught_none', 'del None[0]\n')
        self.check('uncaught_builtin', 'del len[0]\n')
        self.check('uncaught_str_tuple', 'del "ab"[(1, 2)]\n')


if __name__ == '__main__':
    unittest.main()
