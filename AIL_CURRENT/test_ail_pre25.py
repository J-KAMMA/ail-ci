"""A dict built from a keys-only mapping uses keys() and __getitem__, like CPython.

The general path fed any non-dict argument to its pair iterator. A class with keys() and
__getitem__ but no __iter__ (the mapping protocol) therefore ended in
`TypeError: 'instance' object is not iterable`, and a class whose keys() and __iter__
disagree was built from the wrong protocol. dict(m), dict.update(m) and
defaultdict(factory, m) now take the mapping path when the object has keys().
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

KEYS_ONLY = r'''class KeysOnly:
    def keys(self):
        return ["a"]

    def __getitem__(self, k):
        return {"a": 1}[k]


class M:
    def __init__(self, ks, vals):
        self.ks = ks
        self.vals = vals

    def keys(self):
        return self.ks

    def __getitem__(self, k):
        return self.vals[k]


def build(x):
    return dict(x)


def main():
    m = KeysOnly()
    print(dict(m))
    d = {}
    d.update(m)
    print(d)
    print(build(M(("x", "y"), {"x": 7, "y": 8})))
    print(dict(M(range(-2, 2), {-2: 20, -1: 10, 0: 0, 1: 10})))
    print(dict(M([], {})))


main()
'''

DISAGREE = r'''class Odd:
    def keys(self):
        return ["a"]

    def __iter__(self):
        return iter(["b"])

    def __getitem__(self, k):
        return {"a": 1, "b": 2}[k]


class Pairs:
    def __iter__(self):
        return iter([("k", 1), ("j", 2)])


def main():
    print(dict(Odd()))
    d = {}
    d.update(Odd())
    print(d)
    print(dict(Pairs()))


main()
'''

ERRORS = r'''class Missing:
    def keys(self):
        return ["a"]

    def __getitem__(self, k):
        raise KeyError(k)


class NonIter:
    def keys(self):
        return 5

    def __getitem__(self, k):
        return 0


class NoGet:
    def keys(self):
        return ["a"]


def main():
    for make in (Missing, NonIter, NoGet):
        try:
            print(dict(make()))
        except Exception as e:
            print(type(e).__name__, e)


main()
'''


def _run_python(directory, name, text):
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


class Pre25MappingTests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre25-') as directory:
            want, want_rc, err = _run_python(directory, slug, text)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_keys_only_mapping(self):
        self.check('keys_only', KEYS_ONLY)

    def test_keys_disagree_with_iter(self):
        self.check('disagree', DISAGREE)

    def test_mapping_errors(self):
        self.check('errors', ERRORS)


if __name__ == '__main__':
    unittest.main()
