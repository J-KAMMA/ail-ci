"""Pre353: a dict subscription by a slice uses the slice as the key, as in CPython 3.12.

The pre328 reviewer recorded as pre-existing that a dict or set sliced as ``d[1:2]`` did not
follow CPython.  Sets really are not subscriptable, but CPython 3.12 made slice objects
hashable, so a dict uses the slice as a key: a missing key raises ``KeyError: slice(1, 2,
None)`` and a present one returns its value.  The general path now builds a slice object for a
dict target (also through an argument, list item, attribute, dict value, alias and a
``slice(...)`` variable) and uses it for lookup, item assignment, deletion and membership.
Lists, strings, tuples, ranges and sets keep their previous behaviour.  Both builds must
match CPython; a case that cannot is refused by name rather than silently mis-evaluated.
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


class Pre353Tests(unittest.TestCase):
    def check(self, name, text, keyerror=False):
        with tempfile.TemporaryDirectory(prefix='ail-pre353-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))
                if keyerror:
                    self.assertEqual(last_line(got.stderr), last_line(want.stderr),
                                     (name, general, got.stderr[-800:]))

    def test_dict_slice_is_a_key(self):
        self.check('missing_caught', '''
d = {1: 2}
try:
    print(d[1:2])
except KeyError as e:
    print('KeyError', e)
''')
        self.check('present', '''
d = {1: 2}
d[3:4] = 'x'
print(d[3:4], d[slice(3, 4)])
''')
        self.check('equal_slices', '''
a = slice(1, 2)
b = slice(1, 2, None)
d = {a: 'ok'}
print(d[b], a == b, len(d))
''')
        self.check('routes', '''
def lookup(container, key):
    try:
        return container[key]
    except KeyError as e:
        return 'KeyError ' + str(e)
class Box:
    pass
box = Box()
box.d = {1: 2}
box.d[slice(3, 4)] = 'w'
d = {1: 2}
d[slice(3, 4)] = 'w'
print(lookup(d, slice(1, 2)))
print(lookup(d, slice(3, 4)))
print(lookup([d][0], slice(3, 4)))
print(lookup(box.d, slice(3, 4)))
print(lookup({'k': d}['k'], slice(3, 4)))
alias = d
print(lookup(alias, slice(1, 2)))
''')
        self.check('dynamic_bounds', '''
d = {}
keys = [(None, None, None), (1, 2, 3), (-1, -2, None), (True, False, None)]
for k in keys:
    a, b, c = k
    d[a:b:c] = k
for k in keys:
    a, b, c = k
    print(k, d[a:b:c])
try:
    d[9:10]
except KeyError as e:
    print('missing', e)
''')
        self.check('assignment_deletion', '''
d = {1: 2}
d[1:2] = 'v'
print(d[1:2])
del d[1:2]
print(len(d))
s = slice(3, 4)
d[s] = 'w'
print(d[s])
del d[s]
print(len(d))
''')
        self.check('membership', '''
s = slice(1, 2)
d = {s: 'v'}
print(s in d)
print(slice(1, 2) in d)
print(slice(2, 3) in d)
''')

        self.check('counter_and_defaultdict', '''
from collections import Counter, defaultdict
c = Counter()
print(c[1:2])
c[3:4] = 7
print(c[3:4], slice(3, 4) in c)
d = defaultdict(list)
print(d[1:2])
d[3:4].append('x')
print(d[3:4])
del d[3:4]
print(len(d))
''')

    def test_uncaught_key_errors_match(self):
        self.check('missing', 'd = {1: 2}\nprint(d[1:2])\n', keyerror=True)
        self.check('empty', 'd = {}\nprint(d[1:2])\n', keyerror=True)

    def test_other_slices_unchanged(self):
        self.check('sequences', '''
print([1, 2, 3][1:2])
print('abc'[1:2])
print((1, 2, 3)[::-1])
print(list(range(5))[1:4:2])
''')
        self.check('set_is_not_subscriptable', '''
s = {1, 2}
try:
    print(s[1:2])
except TypeError as e:
    print('TypeError', e)
''')
        self.check('set_uncaught', 's = {1, 2}\nprint(s[1:2])\n', keyerror=True)


if __name__ == '__main__':
    unittest.main()
