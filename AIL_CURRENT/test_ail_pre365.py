"""pre365: Counter.__delitem__ ignores a missing key, as CPython 3.12 does.

The pre353 reviewer recorded as pre-existing that deleting a missing key from a
``collections.Counter`` raised ``KeyError`` on both builds, where CPython's
``Counter.__delitem__`` only removes a key that is present.  The general-path runtime's
``ail_dict_del`` now leaves a missing key alone when the dict's Counter flag is set; a plain
dict and a defaultdict still raise KeyError, and a present key (including one whose count is
zero) is removed as before.
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
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


class Pre365Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre365-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_missing_key_deletion_direct(self):
        self.check('direct', '''
from collections import Counter


def main():
    c = Counter()
    c['a'] = 1
    c['b'] = 2
    del c['missing']
    print(c)
    del c['a']
    print(c)
    del c['a']
    print(c)

    d = Counter('aabb')
    del d['z']
    print(d)
    del d['a']
    print(d)

    e = Counter([1, 1, 2, 3])
    del e[9]
    print(e)
    e[5] = 0
    del e[5]
    print(e)

    f = Counter()
    f[-1] = 3
    f[7] = 1
    del f[-2]
    del f[9]
    print(f)
    del f[-1]
    print(f)


main()
''')

    def test_missing_key_deletion_routes(self):
        self.check('routes', '''
from collections import Counter


def drop(c, k):
    del c[k]


def same(c):
    return c


def main():
    c = Counter('aabbc')
    alias = c
    del alias['z']
    print(c)
    drop(c, 'q')
    print(c)
    drop([c][0], 'y')
    print(c)
    drop({'k': c}['k'], 'x')
    print(c)
    drop(same(c), 'w')
    print(c)
    for k in ['v', 'a', 'v', 'b']:
        del c[k]
        print(k, c)


main()
''')

    def test_missing_key_deletion_through_an_attribute(self):
        self.check('attribute', '''
from collections import Counter


class Box:
    pass


def main():
    b = Box()
    b.c = Counter('aab')
    del b.c['missing']
    print(b.c)
    del b.c['a']
    print(b.c)
    del b.c['a']
    print(b.c)


main()
''')

    def test_plain_dict_and_defaultdict_still_raise(self):
        self.check('controls', '''
from collections import Counter, defaultdict


def main():
    d = {'a': 1}
    try:
        del d['missing']
    except KeyError as e:
        print('dict', e)
    del d['a']
    print(d)

    dd = defaultdict(int)
    dd['a'] = 1
    try:
        del dd['missing']
    except KeyError as e:
        print('defaultdict', e)
    del dd['a']
    print(dd)

    c = Counter('aab')
    del c['missing']
    print(c)


main()
''')


if __name__ == '__main__':
    unittest.main()
