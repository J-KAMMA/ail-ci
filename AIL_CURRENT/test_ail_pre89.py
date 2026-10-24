"""Differential checks for the pre-existing fuzz94 review findings.

p13: a nested `def` with a mutable literal default copied the literal at every call, so
`f(1), f(2)` printed `[1] [2]` where CPython shares the list built when the `def` ran and prints
`[1] [1, 2]`. It is now refused by name on both builds. p18 (a callable stored in an instance
attribute) and p23 (keyword arguments through a function value) stay refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MUTABLE_DEFAULTS = {
    'list': '''
def main():
    def f(x, acc=[]):
        acc.append(x)
        return list(acc)
    print(f(1), f(2))


main()
''',
    'dict': '''
def main():
    def f(k, seen={}):
        seen[k] = len(seen)
        return dict(seen)
    print(f("a"), f("b"))


main()
''',
    'set': '''
def main():
    def f(x, seen=set()):
        seen.add(x)
        return sorted(seen)
    print(f(1), f(2))


main()
''',
    'tuple_of_list': '''
def main():
    def f(x, acc=([],)):
        acc[0].append(x)
        return acc[0]
    print(f(1), f(2))


main()
''',
    'kwonly': '''
def main():
    def f(x, *, acc=[]):
        acc.append(x)
        return list(acc)
    print(f(1), f(2))


main()
''',
}

MATCHING_DEFAULTS = '''
def f(x, acc=[1]):
    acc.append(x)
    return list(acc)


def main():
    def g(x, n=10):
        return x + n
    print(f(2), f(3), g(1), g(2, n=3))


main()
'''

INSTANCE_ATTRIBUTE_CALL = '''
class Box:
    pass


def inc(x):
    return x + 1


box = Box()
box.f = inc
print(box.f(2))
'''

KEYWORDS_THROUGH_VALUE = '''
def h(x):
    return x + 1


def call(f):
    return f(x=2)


print(call(h))
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general, run=True):
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
    if not run:
        return True, ''
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre89Tests(unittest.TestCase):
    def test_p13_mutable_literal_defaults_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre89-') as directory:
            for slug, text in MUTABLE_DEFAULTS.items():
                want, want_rc, err = _cpython(directory, 'p13_' + slug, text)
                self.assertEqual(want_rc, 0, err)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, 'p13_%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNone(got, 'p13 %s built (general=%s)\n%s' % (slug, general, build_err))
                    self.assertIn('mutable literal default', build_err, 'p13 %s (general=%s)' % (slug, general))

    def test_p13_immutable_and_top_level_mutable_defaults_match(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre89-') as directory:
            want, want_rc, err = _cpython(directory, 'defaults', MATCHING_DEFAULTS)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, 'defaults_%s' % ('g' if general else 'd'),
                                                MATCHING_DEFAULTS, general)
                self.assertIsNotNone(got, build_err)
                self.assertEqual(got, (want, want_rc), 'general=%s\n%s' % (general, build_err))

    def test_p18_and_p23_stay_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre89-') as directory:
            for slug, text, needle in (
                    ('p18', INSTANCE_ATTRIBUTE_CALL, 'method .f()'),
                    ('p23', KEYWORDS_THROUGH_VALUE, 'keyword arguments in a call through a function value')):
                for general in (True, False):
                    built, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                      text, general, run=False)
                    self.assertIsNone(built, '%s built (general=%s)' % (slug, general))
                    self.assertIn(needle, build_err, '%s (general=%s)' % (slug, general))


if __name__ == '__main__':
    unittest.main()
