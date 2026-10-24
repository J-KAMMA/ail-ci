"""Pre-existing difference from CPython recorded by the pre141 reviewer.

A direct call of a nested `def` textually before that def printed the function's result; CPython
reads the still-unbound local and raises UnboundLocalError. The general path now keeps a def-time
binding flag and the call checks it; the typed path refuses the shape by name, so the default
build falls back to the general path. Calls after the def, recursion, caught errors and values
reaching the function through an argument, a list item or a dict value stay as CPython has them.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'forward_call': '''
def main():
    print(f())
    def f():
        return 1
    print(f())


main()
''',
    'caught_forward_call': '''
def main():
    try:
        f()
    except NameError as e:
        print(type(e).__name__, e)
    def f():
        return 2
    print(f())


main()
''',
    'parameter_same_name': '''
def helper():
    return 9


def main(f):
    print(f())
    def f():
        return 9
    print(f())


main(helper)
''',
    'parameter_same_name_with_args': '''
def helper(x):
    return x * 2


def main(f):
    print(f(3))
    def f(x):
        return x + 1
    print(f(3))


main(helper)
''',
    'assignment_before_def': '''
def helper():
    return 7


def main():
    f = helper
    print(f())
    def f():
        return 1
    print(f())


main()
''',
    'rebind_after_def': '''
def helper():
    return 9


def main():
    def f():
        return 1
    print(f())
    f = helper
    print(f())


main()
''',
    'except_as_then_def': '''
def main():
    try:
        raise ValueError("x")
    except ValueError as f:
        try:
            print(f())
        except TypeError as e:
            print(type(e).__name__)
    def f():
        return 1
    print(f())


main()
''',
    'call_after_def_and_recursion': '''
def main():
    def f(n):
        if n <= 0:
            return 0
        return 1 + f(n - 1)
    print(f(3))
    print(f(0))


main()
''',
    'argument_side_effect': '''
def bump():
    print("arg")
    return 1


def main():
    print(f(bump()))
    def f(x):
        return x


main()
''',
    'alias_through_argument_list_and_dict': '''
def take(x):
    return x()


def main():
    def f():
        return 3
    print(take(f), [f][0](), {"f": f}["f"]())


main()
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


class Pre165Tests(unittest.TestCase):
    def test_forward_nested_call_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre165-') as directory:
            for slug, text in PROGRAMS.items():
                want, want_rc = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                     % (slug, general, build_err))

    def test_forward_call_names_unbound_local(self):
        text = PROGRAMS['forward_call']
        with tempfile.TemporaryDirectory(prefix='ail-pre165-') as directory:
            for general in (True, False):
                got, err = _build_and_run(directory, 'unbound_%s' % ('g' if general else 'd'),
                                          text, general)
                self.assertIsNotNone(got, err)
                self.assertEqual(got[1], 1)
                self.assertIn('UnboundLocalError', err)
                self.assertIn("cannot access local variable 'f'", err)


if __name__ == '__main__':
    unittest.main()
