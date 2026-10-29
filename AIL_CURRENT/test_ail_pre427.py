"""pre427: a lambda with a positional-only parameter is refused by name on both builds.

The pre413 review listed the posonly/kwonly/vararg lambda subset refusals as unverified.  A
positional-only lambda was not refused on every route: the map()/key= lowering read only
``args.args``, so ``lambda x, /, y: y`` lost ``x``.  CPython raises TypeError for
``map(lambda x, /, y: y, [5])`` (the one argument binds to ``x`` and ``y`` is missing), while
both builds returned ``[5]``.  Every lambda with a positional-only parameter is now named at
compile time; a plain lambda, a positional-only ``def`` and a vararg ``def`` keep matching
CPython, and the existing kwonly/vararg lambda refusals stay refusals.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MATCHING = {
    'plain_map': '''
print(list(map(lambda x: x * 2, [1, 2, 3])))
''',
    'plain_key': '''
print(sorted([3, 1, 2], key=lambda x: -x))
''',
    'def_posonly': '''
def f(x, /):
    return x + 1
print(f(2))
''',
    'def_posonly_default': '''
def g(a, b=10, /):
    return a + b
print(g(1), g(1, 2))
''',
    'def_vararg': '''
def h(*a):
    return a
print(h(), h(1, 2))
''',
}

REFUSALS = {
    'map_ignored_posonly': '''
print(list(map(lambda x, /, y: y * 2, [5])))
''',
    'key_ignored_posonly': '''
print(sorted([3, 1, 2], key=lambda x, /, y: y))
''',
    'map_two_posonly': '''
print(list(map(lambda x, y, /: x + y, [1, 2])))
''',
    'key_two_posonly': '''
print(sorted([3, 1, 2], key=lambda x, y, /: x + y))
''',
    'direct_single': '''
print((lambda x, /: x + 1)(2))
''',
    'key_single': '''
print(sorted([3, 1, 2], key=lambda x, /: -x))
''',
    'reduce_mixed': '''
from functools import reduce
print(reduce(lambda a, /, b: a + b, [1, 2, 3]))
''',
    'function_local': '''
def f():
    g = lambda x, /: x + 1
    return g(2)
print(f())
''',
    'default': '''
def h(f=lambda x, /: x + 1):
    return f(2)
print(h())
''',
    'kwonly_lambda': '''
print((lambda x, *, k: x + k)(1, k=2))
''',
    'vararg_lambda': '''
print((lambda *a: a)(1, 2))
''',
}


def _run_cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=1200, env=env)


def _build_and_run(directory, name, text, general):
    exe, built = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace')[-1500:])


class Pre427Tests(unittest.TestCase):
    def test_matching_programs(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre427-') as directory:
            for slug, text in MATCHING.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_positional_only_lambda_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre427-') as directory:
            for slug, text in REFUSALS.items():
                _run_cpython(directory, slug, text)
                for general in (True, False):
                    _, built = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, '%s (general=%s)\n%s' %
                                        (slug, general, output))
                    self.assertIn('not in the subset', output, '%s (general=%s)\n%s' %
                                  (slug, general, output))
                    if slug not in ('kwonly_lambda', 'vararg_lambda'):
                        self.assertIn('positional-only parameter', output,
                                      '%s (general=%s)\n%s' % (slug, general, output))
                    self.assertNotIn('RecursionError', output, '%s (general=%s)\n%s' %
                                     (slug, general, output))


if __name__ == '__main__':
    unittest.main()
