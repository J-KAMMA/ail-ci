"""Pre-existing difference from CPython found while reviewing fuzz94 (nested functions).

A nested `def` whose literal default is a list, dict, set or a tuple holding one was rebuilt at
every call site, so each call got a fresh object where CPython shares the object built when the
`def` statement ran: `def f(x, acc=[]); f(1); f(2)` printed `[1] [2]` instead of `[1] [1, 2]`.
Such a nested default is now evaluated once at the `def` into a hidden local, so the object is
shared between calls as in CPython. Immutable defaults, including values that reach the call through
an argument, a list item, a dict value and an attribute, still agree.
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
    print(f(1), f(2), f(3))


main()
''',
    'empty_list': '''
def main():
    def f(x, acc=[]):
        acc.append(x)
        return acc
    print(f(1))


main()
''',
    'dict': '''
def main():
    def f(k, d={}):
        d[k] = d.get(k, 0) + 1
        return dict(d)
    print(f("a"), f("b"), f("a"))


main()
''',
    'set': '''
def main():
    def f(x, seen=set()):
        seen.add(x)
        return len(seen)
    print(f(1), f(2), f(1))


main()
''',
    'tuple_of_list': '''
def main():
    def f(x, acc=([],)):
        acc[0].append(x)
        return list(acc[0])
    print(f(1), f(2))


main()
''',
    'keyword_only': '''
def main():
    def f(x, *, acc=[]):
        acc.append(x)
        return list(acc)
    print(f(1), f(2))


main()
''',
}

IMMUTABLE_DEFAULTS = '''
class C:
    def __init__(self):
        self.v = 42


def main():
    c = C()
    xs = [c.v]
    d = {"k": c.v}

    def f(a, b=-5, big=2147483647, empty=(), t=(1, 2), s="x"):
        return (a, b, big, empty, t, s)

    print(f(xs[0]))
    print(f(d["k"], -7, s="y"))
    print(f(c.v, b=0, t=()))


main()
'''


def _cpython(directory, name, text):
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


class Pre117Tests(unittest.TestCase):
    def test_mutable_literal_defaults_of_nested_defs_are_shared(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre117-') as directory:
            for slug, text in MUTABLE_DEFAULTS.items():
                want, want_rc, err = _cpython(directory, slug, text)
                self.assertEqual(want_rc, 0, err)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                     % (slug, general, build_err))

    def test_immutable_defaults_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre117-') as directory:
            want, want_rc, err = _cpython(directory, 'immutable', IMMUTABLE_DEFAULTS)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, 'immutable_%s' % ('g' if general else 'd'),
                                                IMMUTABLE_DEFAULTS, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, want_rc), 'general=%s\n%s' % (general, build_err))


if __name__ == '__main__':
    unittest.main()
