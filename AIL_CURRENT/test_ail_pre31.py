"""Pre31: int() of a float outside int64 is refused by name, not stopped as a generic overflow.

CPython has unbounded integers, so `int(1e300)` prints a 301-digit integer. This language's ints
are signed int64 (SEMANTICS.md), so a float whose truncation does not fit has no answer here. The
front end now refuses such a conversion when the float is a literal, a module constant or a literal
reached through an argument, a list item, a tuple item or a dict value, naming the construct and the
value instead of compiling a program that dies with `integer overflow`. Values that fit int64, and
conversions whose float only reaches int() at run time, are unchanged and still compared with CPython.
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
    with tempfile.TemporaryDirectory(prefix='ail-pre31-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertIn('big integer', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre31-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'flow_out': 'x = 1e300\nprint(int(x))\n',
    'literal': 'print(int(1e300))\n',
    'negative_literal': 'print(int(-1e300))\n',
    'negative_name': 'x = -1e300\nprint(int(x))\n',
    'through_argument': 'def identity(x):\n    return x\n\n\nprint(int(identity(1e300)))\n',
    'through_wrapper': 'def take(x):\n    return int(x)\n\n\nprint(take(1e300))\n',
    'list_item': 'print(int([1e300][0]))\n',
    'tuple_item': 'print(int((1e300,)[0]))\n',
    'dict_value': 'print(int({"v": 1e300}["v"]))\n',
    'upper_bound': 'print(int(1e19))\n',
}

MATCH = {
    'within_int64': '''
class C:
    def __init__(self):
        self.v = 9.0e18


def take(x):
    return int(x)


items = [1.9, -1.9]
d = {"v": 9.0e18}
c = C()
print(int(1.9), int(-1.9), int(0.0), int(-0.0))
print(int(9.0e18), int(-9.0e18), int(9223372036854774784.0), int(-9223372036854774784.0))
print(int(items[0]), int(items[1]))
print(int(d["v"]))
print(int(c.v))
print(take(1.9), take(-1.9))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatOutsideInt64(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_conversions_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
