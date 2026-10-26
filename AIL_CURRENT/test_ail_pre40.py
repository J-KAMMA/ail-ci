"""Pre40: an int64-out-of-range float read through a module global is refused by name.

CPython has unbounded integers, so `x = 1e300; int(x)` prints a 301-digit integer. This
language's ints are signed int64, so the front end refuses a conversion that it can see is
outside int64, including a module constant read through `global x` in a function. Reads that
see a rebound or fitting value keep matching CPython.
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
    with tempfile.TemporaryDirectory(prefix='ail-pre40-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertIn('big integer', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre40-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'global_read': 'x = 1e300\n\ndef f():\n    global x\n    return int(x)\n\nprint(f())\n',
    'global_read_plain': 'x = 1e300\n\ndef f():\n    return int(x)\n\nprint(f())\n',
    'global_negative': 'x = -1e300\n\ndef f():\n    global x\n    return int(x)\n\nprint(f())\n',
    'global_expression': 'x = 1e300\n\ndef f():\n    global x\n    return int(x + 1)\n\nprint(f())\n',
    'global_container': 'x = 1e300\n\ndef f():\n    global x\n    return int([x][0])\n\nprint(f())\n',
    'global_identity': ('x = 1e300\n\ndef identity(y):\n    return y\n\n'
                        'def f():\n    global x\n    return int(identity(x))\n\nprint(f())\n'),
    'global_upper_bound': ('x = 9223372036854775808.0\n\ndef f():\n    global x\n'
                           '    return int(x)\n\nprint(f())\n'),
}

MATCH = {
    'global_in_range': 'x = 1.5\n\ndef f():\n    global x\n    return int(x)\n\nprint(f())\n',
    'global_negative_edge': ('x = -9223372036854775808.0\n\ndef f():\n    global x\n'
                             '    return int(x)\n\nprint(f())\n'),
    'global_rebound_before_read': ('x = 1e300\n\ndef f():\n    global x\n    x = 1.5\n'
                                   '    return int(x)\n\nprint(f())\n'),
    'global_mutated_elsewhere': ('x = 1e300\n\ndef setx():\n    global x\n    x = 1.5\n\n'
                                 'def f():\n    global x\n    setx()\n    return int(x)\n\nprint(f())\n'),
    'global_expression_fits': ('x = 1e300\n\ndef f():\n    global x\n'
                               '    return int(x * 0)\n\nprint(f())\n'),
    'global_container_fits': ('x = 1e300\n\ndef f():\n    global x\n'
                              '    return int([x, 1.5][1])\n\nprint(f())\n'),
    'global_param_shadow': 'x = 1e300\n\ndef f(x):\n    return int(x)\n\nprint(f(1.5))\n',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatGlobalOutsideInt64(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_conversions_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
