"""A reversed generator expression raises CPython's TypeError (DIFFERENCES C?-pre11-10240012-1).

The tuple pass used to hoist `((x, x) for x in ...)` to a plain list, so `reversed()` saw a list and
silently printed the reversed items. A generator expression is not reversible: CPython evaluates only
its outermost iterable, then raises TypeError ("'generator' object is not reversible"). The general
path now does the same, and the typed path refuses the construct by name so the default build falls
back to it.

Both builds must match CPython's stdout, exit status and last stderr line; a list, tuple, range or str
stays reversible.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip()]
    return lines[-1] if lines else ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return exe, built


def check_program(test, name, text, modes=(True, False)):
    """stdout, exit status and the last stderr line match CPython."""
    with tempfile.TemporaryDirectory(prefix='ail-pre11-') as directory:
        want = _cpython(directory, name, text)
        for general in modes:
            exe, built = _build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, '%s (general=%s)\n%s'
                             % (text[:2000], general, (built.stdout + built.stderr)[-1500:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), want,
                             '%s (general=%s)\n%s' % (text[:2000], general, got.stderr.decode('utf-8', 'replace')[-800:]))


def check_typed_refused(test, name, text):
    """With the general path disabled, the construct is refused by name; the default build falls back."""
    with tempfile.TemporaryDirectory(prefix='ail-pre11-') as directory:
        src = Path(directory) / (name + '.ail')
        src.write_text(text, encoding='utf-8')
        env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1', AIL_NO_GENERAL='1')
        env.pop('AIL_UNIFIED_FORCE', None)
        built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', name + '.typed'], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
        test.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
        test.assertNotIn('Traceback', built.stderr)
        test.assertIn('generator expression', built.stdout + built.stderr)
        test.assertIn('reversed', built.stdout + built.stderr)


GENERATOR_EXPRESSIONS = {
    'tuple': 'print(list(reversed((x, x) for x in [1, 2, 3])))\n',
    'plain': 'print(list(reversed(x for x in "abc")))\n',
    'empty': 'print(list(reversed(x for x in [])))\n',
    'condition': 'print(list(reversed((x, x) for x in range(6) if x % 2)))\n',
    'two_loops': 'print(list(reversed((x, y) for x in [1, 2] for y in [3, 4])))\n',
    'nested': 'print(list(reversed((x for x in (y for y in [1, 2])))))\n',
    'outer_called_once': ('def outer():\n    print("outer")\n    return [1, 2, 3]\n\n\n'
                          'def body(x):\n    print("body", x)\n    return x\n\n\n'
                          'print(list(reversed((body(x) for x in outer()))))\n'),
    'outer_not_iterable': 'print(list(reversed((x for x in 5))))\n',
}

REVERSIBLE = ('print(list(reversed([1, 2, 3])))\n'
              'print(list(reversed((1, 2, 3))))\n'
              'print(list(reversed(range(4))))\n'
              'print(list(reversed("abc")))\n'
              'print([x for x in reversed([1, 2])])\n')


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class ReversedGeneratorExpression(unittest.TestCase):
    def test_generator_expressions_raise_like_cpython(self):
        for name, text in sorted(GENERATOR_EXPRESSIONS.items()):
            with self.subTest(name=name):
                check_program(self, 'gen_' + name, text)

    def test_reversible_sequences_still_work(self):
        check_program(self, 'reversible', REVERSIBLE)

    def test_the_typed_path_refuses_by_name_and_the_default_build_falls_back(self):
        text = ('def main():\n    print(list(reversed((x, x) for x in [1, 2, 3])))\n\n\nmain()\n')
        check_typed_refused(self, 'typed_tuple_gen', text)
        check_program(self, 'default_tuple_gen', text, modes=(False,))


if __name__ == '__main__':
    unittest.main()
