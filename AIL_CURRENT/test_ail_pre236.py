"""pre236: large special exponents and absorbing zero are decided before the fold guard.

The rbpre190 review recorded that the generic all-constant folder still refused the
special power bases and an absorbing zero once an operand exceeded its 2**20-bit limit
(for example `0 ** (1 << 2000000)` and `0 * (1 << 2000000)`), although CPython reduces
them to int64 values.  The generic folder now decides those cases before the size guard,
as `pyfront.int_constant` already did, and retries a huge exponent of 0/1/-1 at the
special 2**24-bit limit so its sign and parity are known.  A still wider special
exponent and a genuinely large non-special intermediate stay refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SPECIAL_REDUCTIONS = r'''A = 0 ** (1 << 2000000)
B = 1 ** (1 << 2000000)
C = (-1) ** ((1 << 2000000) + 1)


class Box:
    def __init__(self):
        self.n = 0
    m = 1 ** (1 << 2000000)


def defaulted(x=(-1) ** (1 << 2000000)):
    return x


def identity(v):
    return v


def main():
    print(A, B, C, Box.m, defaulted())
    print(0 * (1 << 2000000))
    print((1 << 2000000) * 0)
    print(0 & (1 << 2000000))
    print((1 << 2000000) & 0)
    print(0 ** (1 << 2000000))
    print(1 ** (1 << 2000000))
    print((-1) ** (1 << 2000000))
    print((-1) ** ((1 << 2000000) + 1))
    print(identity(0 ** (1 << 2000000)))
    xs = [1 ** (1 << 2000000)]
    print(xs[0])
    box = Box()
    box.n = (-1) ** ((1 << 2000000) + 1)
    print(box.n)
    d = {"n": 0 * (1 << 2000000)}
    print(d["n"])


main()
'''

ZERO_BEYOND_SPECIAL = r'''print(0 * (1 << 16777216))
print((1 << 16777216) * 0)
print(0 & (1 << 16777216))
print((1 << 16777216) & 0)
'''

REFUSALS = [
    ('wide_special', 'print(1 ** (1 << 16777216))\n',
     'outside the signed 64-bit range'),
    ('wide_shift', 'print((1 << 4194304) >> 4194304)\n',
     'outside the signed 64-bit range'),
    ('wide_maxsplit', 'print("a b".split(" ", (1 << 1048576) >> 1048576))\n',
     'maxsplit constant does not fit'),
]

MODES = (
    ('default', {}),
    ('general', {'AIL_UNIFIED_FORCE': '1'}),
)


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=300,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, extra):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_UNIFIED_FORCE', 'AIL_UNIFIED', 'AIL_IR', 'AIL_NO_GENERAL'):
        env.pop(key, None)
    env.update(extra)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=300, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre236Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre236-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for mode, extra in MODES:
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, mode), text, extra)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (text[:2000], mode, build_err))
                self.assertEqual(got, (want, rc), '%s (%s)\n%s' % (text[:2000], mode, build_err))

    def check_refused(self, slug, text, needle):
        # exact ints (bigint): built on both paths, same (stdout, returncode) as CPython
        with tempfile.TemporaryDirectory(prefix='ail-pre236-') as directory:
            want, rc, _err = _cpython(directory, slug, text)
            for mode, extra in MODES:
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, mode), text, extra)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (text[:200], mode, build_err))
                self.assertEqual(got, (want, rc), '%s (%s)\n%s' % (text[:200], mode, build_err))

    def test_special_exponent_and_zero_reductions(self):
        self.check('special_reductions', SPECIAL_REDUCTIONS)

    def test_absorbing_zero_beyond_special_limit(self):
        self.check('zero_beyond_special', ZERO_BEYOND_SPECIAL)

    def test_wide_constants_still_refused_by_name(self):
        for slug, text, needle in REFUSALS:
            self.check_refused(slug, text, needle)


if __name__ == '__main__':
    unittest.main()
