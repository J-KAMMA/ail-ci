"""pre309: hash() of a frozenset uses CPython's element hashes.

The rbrbpre245 reviewer recorded `hash(frozenset([1, 2]))` as a pre-existing difference: the
v2 runtime mixed the set's private table hashes, so it printed a different integer from CPython
(7543283827113604033 vs -1826646154956904602).  hash() now applies CPython's frozenset mix to
the elements' Python hash values, so int, bool, None, float, tuple and nested-frozenset elements
match CPython.  A frozenset of tuples used to be lowered to a tuple table whose instance hash was
its identity; hash() on such a value now stays on the general path, where the real frozenset is
hashed.  Strings keep CPython's per-process randomised hash, so only their order independence is
checked.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'basic': '''
print(hash(frozenset()))
print(hash(frozenset([1])))
print(hash(frozenset([1, 2])))
print(hash(frozenset([2, 1])))
print(hash(frozenset([0, -1, -2])))
print(hash(frozenset([True, False])))
print(hash(frozenset([2**62, -2**62, 2**63 - 1, -2**63])))
print(hash(frozenset([1, 2])) == hash(frozenset([2, 1])))
''',
    'other_types': '''
print(hash(frozenset([None])))
print(hash(frozenset([None, 1, 2])))
print(hash(frozenset([1.5])))
print(hash(frozenset([-0.0, 0.0])))
print(hash(frozenset([2.0, 3.0])))
print(hash(frozenset([float('inf'), float('-inf')])))
print(hash(frozenset([(1, 2)])))
print(hash(frozenset([(1, 2), (3, 4)])))
print(hash(frozenset([frozenset([1, 2])])))
print(hash(frozenset([1, frozenset([2, 3]), (4, 5)])))
''',
    'routes': '''
class Box:
    pass


def take(x):
    return hash(x)


box = Box()
box.fs = frozenset([1, 2])
d = {'k': frozenset([3, 4])}
items = [frozenset([5, 6])]
alias = frozenset([1, 2])
print(hash(frozenset(range(5))))
print(take(frozenset([7, 8])))
print(hash(items[0]))
print(hash(box.fs))
print(hash(d['k']))
print(hash(alias))
print(alias is box.fs)
box.fs = frozenset([9])
print(hash(box.fs), hash(alias))
print([hash(frozenset([i, i + 1])) for i in range(3)])
''',
    'semantics': '''
a = frozenset([1, 2])
b = frozenset([2, 1])
print(hash(a) == hash(b), len(a), a == b)
d = {a: 'yes'}
print(d[b], b in d, a in {frozenset([1, 2])})
print(hash(frozenset([1, 2])) == hash(frozenset([1, 2])))
print(hash(frozenset([1, 2])), hash(frozenset([1, 2, 3])))
s = set()
s.add(b)
print(a in s, len(s))
try:
    hash(set([(1, 2)]))
except Exception as e:
    print(type(e).__name__, str(e))
''',
    'strings': '''
a = frozenset(['a', 'b', 'c'])
b = frozenset(['c', 'b', 'a'])
print(hash(a) == hash(b))
print(hash(a) == hash(a))
print(len({a: 1}))
print(b in {a: 1})
''',
}


def _run_cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


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
                           capture_output=True, text=True, timeout=1200, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre309Tests(unittest.TestCase):
    def test_frozenset_hash_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre309-') as directory:
            for slug, text in PROGRAMS.items():
                want, want_rc = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                     % (slug, general, build_err))


if __name__ == '__main__':
    unittest.main()
