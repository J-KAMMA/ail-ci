"""fz1: an exception raised in a try's ``else`` clause reaches an OUTER handler.

The daily fuzzer (seed 2075200054) found a program whose try/else body raised
``ValueError`` from ``int('Cd')``; CPython ended with the uncaught exception, while AIL
printed the program's later lines.  The general emitter copied the ``else`` statements into
the same C block as the ``try`` body, so the try's own handlers caught them.  They now run
after the handler dispatch and are compiled against the enclosing handlers (and against the
temporary finally trampoline when there is a ``finally``), so the value from an argument, a
list item, an attribute or a dict value follows CPython on both builds.
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


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-fz1-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


PROGRAMS = {
    'argument': '''
def f(s):
    try:
        print('body')
    except ValueError:
        print('caught')
    else:
        print(int(s))
    print('after')


f('Cd')
''',
    'list_item': '''
def f(xs):
    try:
        pass
    except ValueError:
        print('caught')
    else:
        print(int(xs[0]))
    print('after')


f(['Cd'])
''',
    'attribute': '''
class Box:
    def __init__(self, v):
        self.v = v


def f(b):
    try:
        pass
    except ValueError:
        print('caught')
    else:
        print(int(b.v))
    print('after')


f(Box('Cd'))
''',
    'dict_value': '''
def f(d):
    try:
        pass
    except ValueError:
        print('caught')
    else:
        print(int(d['k']))
    print('after')


f({'k': 'Cd'})
''',
    'index_outer': '''
try:
    try:
        print('body')
    except IndexError:
        print('inner')
    else:
        print('ab'[3])
except IndexError:
    print('outer')
print('after')
''',
    'zero_outer': '''
try:
    try:
        x = 1
    except ZeroDivisionError:
        print('inner')
    else:
        print(1 // 0)
except ZeroDivisionError:
    print('outer')
print('after')
''',
    'finally_outer': '''
try:
    try:
        print('body')
    except ValueError:
        print('inner')
    else:
        print(int('Cd'))
    finally:
        print('finally')
except ValueError:
    print('outer')
print('after')
''',
    'else_success': '''
def f(n):
    try:
        x = n
    except ValueError:
        print('inner')
    else:
        print('else', x)
    finally:
        print('fin')
    print('after')


f(3)
''',
    'body_error_skips_else': '''
try:
    try:
        print(int('Cd'))
    except ValueError:
        print('caught')
    else:
        print('else')
    finally:
        print('fin')
except ValueError:
    print('outer')
print('after')
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class TryElseExceptionScope(unittest.TestCase):
    def test_else_exception_scope(self):
        for name, text in sorted(PROGRAMS.items()):
            check_program(self, name, text)


if __name__ == '__main__':
    unittest.main()
