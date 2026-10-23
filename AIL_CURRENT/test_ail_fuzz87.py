"""Fuzz round 87: closures and late binding.

A nested `def` inside a function is not a value on the general path: its defaults are filled in
at each call site.  A literal mutable default (`def make(x, acc=[])` inside `main`) was therefore
a fresh list/dict at every call, while CPython evaluates it once when the `def` runs:

    def main():
        def make(x, acc=[]):
            acc.append(x)
            return acc
        print(make(1), make(2), make(3))

printed `[1] [2] [3]` instead of `[1, 2, 3] [1, 2, 3] [1, 2, 3]` (both builds; the typed path
falls back to the general path for this shape).  Such a default is now refused by name on the
general path, so the default build refuses it too.  Immutable nested defaults and late binding
over a loop variable still match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


MUTABLE_LIST = '''def main():
    def make(x, acc=[]):
        acc.append(x)
        return acc
    print(make(1), make(2), make(3))


main()
'''

MUTABLE_DICT = '''def main():
    def tally(k, seen={}):
        seen[k] = seen.get(k, 0) + 1
        return seen[k]
    print(tally("a"), tally("a"), tally("b"))


main()
'''

MUTABLE_KEYWORD_ONLY = '''def main():
    def add(x, *, buf=[]):
        buf.append(x)
        return len(buf)
    print(add(1), add(2))


main()
'''

SAFE = '''def main():
    def show(x, y=1, z=None, tag="t", pair=(1, 2)):
        return (x, y, z, tag, pair)
    print(show(1), show(1, 2, 3), show(1, tag="q"))
    fs = []
    for i in range(3):
        fs.append(lambda: i)
    print([f() for f in fs])
    gs = [lambda i=i: i for i in range(3)]
    print([g() for g in gs])


main()
'''


def _cpython(directory, name, text):
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
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz87Tests(unittest.TestCase):
    def check_refused(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz87-') as directory:
            _, rc = _cpython(directory, name, text)
            self.assertEqual(rc, 0)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (name, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNone(got, build_err)
                self.assertIn('mutable default', build_err)

    def check_same(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz87-') as directory:
            want, rc = _cpython(directory, name, text)
            self.assertEqual(rc, 0)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (name, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text, general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text, general, build_err))

    def test_nested_mutable_list_default_is_refused(self):
        self.check_refused('mutable_list', MUTABLE_LIST)

    def test_nested_mutable_dict_default_is_refused(self):
        self.check_refused('mutable_dict', MUTABLE_DICT)

    def test_nested_mutable_keyword_only_default_is_refused(self):
        self.check_refused('mutable_kwonly', MUTABLE_KEYWORD_ONLY)

    def test_immutable_defaults_and_late_binding_still_match(self):
        self.check_same('safe', SAFE)


if __name__ == '__main__':
    unittest.main()
