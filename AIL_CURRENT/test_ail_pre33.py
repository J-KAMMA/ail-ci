"""pre33: an integer power whose constant result leaves int64 is refused by name.

CPython's int is unbounded, so `10 ** 40` is an exact integer; this language's int is int64
(SEMANTICS section 1). Before this, a constant integer power whose exact result does not fit
reached `ail_ipow` at run time and stopped with `integer overflow`, so a tuple such as
`(10 ** 40,)` never printed, and the v1 general emitter compiled an assigned `x = 10 ** 40` and
then stopped at run time. It is now refused at compile time with a name: either the generic
all-constant folder (`int64 constant out of range`, `outside the signed 64-bit range`) or the
accepted `refuse_int_pow_overflow` check with its DIFFERENCES id
(C?-job-pre33-10240909-1), on both general builds, the typed path and the v1 general emitter.
Powers that fit are unchanged, including INT64_MIN from `(-2) ** 63` and the bases -1, 0 and 1
under a huge exponent.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
MARKER = 'C?-job-pre33-10240909-1'
REFUSALS = ('int64 constant out of range',
            'int64 constant expression out of range',
            'outside the signed 64-bit range',
            MARKER)


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, mode):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if mode == 'g':
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'v1':
        env['AIL_GENERAL'] = 'v1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


REFUSED = {
    'plain': 'def main():\n    print(10**40)\n\n\nmain()\n',
    'in_tuple': 'def main():\n    print((10**40,))\n\n\nmain()\n',
    'through_argument': ('def show(v):\n    print(v)\n\n\ndef main():\n    show(10**40)\n\n\nmain()\n'),
    'list_item': 'def main():\n    xs = [10**40]\n    print(xs[0])\n\n\nmain()\n',
    'local_assignment': 'def main():\n    x = 10**40\n    print(x)\n\n\nmain()\n',
    'attribute': ('class Box:\n    def __init__(self, v):\n        self.v = v\n\n\ndef main():\n'
                  '    b = Box(0)\n    b.v = 10**40\n    print(b.v)\n\n\nmain()\n'),
    'dict_value': 'def main():\n    d = {"k": 10**40}\n    print(d["k"])\n\n\nmain()\n',
    'two_to_63': 'def main():\n    print(2**63)\n\n\nmain()\n',
    'three_to_40': 'def main():\n    print(3**40)\n\n\nmain()\n',
}

MATCH = '''def main():
    print(2**62, (-2)**63, (-2)**62, 0**0)
    print(1**1000000000, (-1)**1000000001)
    print(3**39, (-3)**39, 10**18, (-10)**18)
    print((2**10,), [3**5], {"k": 2**20})
    print(2.0**63, 2**63.0, 2**-1, 10**-3)


main()
'''

MATCH_SOURCES = '''class Box:
    def __init__(self, v):
        self.v = v


def show(v):
    return v


def main():
    xs = [2**10]
    d = {"k": 2**20}
    b = Box(2**30)
    print(show(xs[0]), d["k"], b.v, show(2**40 // 2**20))


main()
'''


class Pre33Tests(unittest.TestCase):
    def test_constant_power_out_of_range_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre33-') as directory:
            for name, text in REFUSED.items():
                for mode in ('g', 'd', 'v1'):
                    with self.subTest(name=name, mode=mode):
                        _, built = build(directory, name + '_' + mode, text, mode)
                        self.assertNotEqual(built.returncode, 0, (name, mode))
                        message = built.stdout + built.stderr
                        self.assertTrue(any(item in message for item in REFUSALS), (name, mode, message))
                        self.assertNotIn('integer overflow', message, (name, mode))

    def test_powers_that_fit_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre33-') as directory:
            for name, text in (('fit', MATCH), ('fit_sources', MATCH_SOURCES)):
                want, rc = cpython(directory, name, text)
                self.assertEqual(rc, 0)
                for mode in ('g', 'd'):
                    exe, built = build(directory, name + '_' + mode, text, mode)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, rc, (name, mode))


if __name__ == '__main__':
    unittest.main()
