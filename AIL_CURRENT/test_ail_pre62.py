"""Pre62: int() of an out-of-int64 float reaching the conversion at run time.

CPython has unbounded integers, so `int(1e300)` prints a 301-digit integer. This language's ints
are signed int64, so the front end refuses a conversion whose float value it can see is outside
int64, naming the construct and the value instead of compiling a program that stops with
`integer overflow`. The earlier checks saw literals, stable module constants, container items and
wrapper arguments; this module pins values that only exist while the program runs: a simple
function's return value, a local (including a closure or an augmented/annotated assignment), a
default argument used by an omitted call, `float("1e300")`, and a keyword method wrapper. Values
that fit int64, non-finite floats, branches and mutated containers stay compared with CPython.
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


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre62-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertIn('big integer', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre62-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'function_return': 'def value():\n    return 1e300\n\n\nprint(int(value()))\n',
    'function_return_negative': 'def value():\n    return -1e300\n\n\nprint(int(value()))\n',
    'function_return_local': 'def value():\n    x = 1e300\n    return x\n\n\nprint(int(value()))\n',
    'function_return_container': 'def value():\n    return {"v": [1e300]}["v"][0]\n\n\nprint(int(value()))\n',
    'runtime_float_string': 'v = float("1e300")\nprint(int(v))\n',
    'default_argument': 'def take(x=1e300):\n    return int(x)\n\n\nprint(take())\n',
    'nested_closure': ('def outer():\n    x = 1e300\n\n    def inner():\n        return int(x)\n'
                       '    return inner()\n\n\nprint(outer())\n'),
    'augmented_assignment': 'def f():\n    x = 0.0\n    x += 1e300\n    return int(x)\n\n\nprint(f())\n',
    'annotated_assignment': 'def f():\n    x: float = 1e300\n    return int(x)\n\n\nprint(f())\n',
    'method_keyword': ('class Box:\n    def take(self, x):\n        return int(x)\n\n\n'
                       'print(Box().take(x=1e300))\n'),
    'keyword_wrapper': 'def take(x):\n    return int(x)\n\n\nprint(take(x=1e300))\n',
    'global_read': 'x = 1e300\n\ndef f():\n    global x\n    return int(x)\n\nprint(f())\n',
    'upper_bound': 'def value():\n    return 9223372036854775808.0\n\n\nprint(int(value()))\n',
}

MATCH = {
    'function_return_in_range': ('def value():\n    return -1.9\n\n\ndef boundary():\n'
                                 '    return -9223372036854775808.0\n\n\n'
                                 'print(int(value()), int(boundary()), int(9.0e18))\n'),
    'default_argument_passed': 'def take(x=1e300):\n    return int(x)\n\n\nprint(take(1.5))\n',
    'int_without_float': 'def value():\n    return 42\n\n\nprint(int(value()), int(-value()))\n',
    'nonfinite': ('def value():\n    return float("inf")\n\n\ntry:\n    print(int(value()))\n'
                  'except OverflowError as error:\n    print(type(error).__name__)\n'),
    'branches': ('def f(flag):\n    x = 1.5\n    if flag:\n        x = 1.5\n    else:\n'
                 '        x = 1e300\n    return int(x)\n\n\nprint(f(True))\n'),
    'mutated_list': ('def f():\n    x = [1e300]\n    x[0] = 1.5\n    return int(x[0])\n\n\n'
                     'print(f())\n'),
    'unknown_dict_key': ('k, = ("a",)\nx = {None: 1e300, "a": 1.5}[k]\n\n\n'
                         'def take(v):\n    return int(v)\n\n\nprint(take(v=x))\n'),
    'global_mutated_elsewhere': ('x = 1e300\n\ndef setx():\n    global x\n    x = 1.5\n\n\n'
                                  'def f():\n    global x\n    setx()\n    return int(x)\n\n\n'
                                  'print(f())\n'),
    'global_in_range': 'x = 1.5\n\ndef f():\n    global x\n    return int(x)\n\nprint(f())\n',
    'expression_that_fits': ('x = 1e300\n\ndef take(x):\n    return int(x)\n\n\n'
                             'print(take(x=1e300 * 0), take(x=1e300 - 1e300))\n'),
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatRuntimeOutsideInt64(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_conversions_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
