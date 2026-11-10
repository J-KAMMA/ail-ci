"""fz246: a fixed-point float field never shows a NaN's sign (already fixed by fz208).

The daily fuzzer (seed 2076623644) printed `str(abs(v1)) + f'{(v1 / (abs(v1) + 1.0)):>10.1f}-'`
after v1 overflowed to infinity: CPython prints `inf       nan-`, while at the fuzz run AIL
printed `inf      -nan-`.  The cause is the one fixed for fz208: glibc's `snprintf("%.*f")`
writes a negative NaN as `-nan`, and CPython never shows a NaN's sign.  On this tree the
difference does not reproduce; this module pins the minimized seed and the same formats for
both NaN signs, values from an argument, a list item, an attribute and a dict value, plus
infinity and `-0.0`, on the default and `AIL_IR=1` builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

MODES = (
    ('default', {}),
    ('default_ir', {'AIL_IR': '1'}),
)

MINIMIZED = '''\
v1 = -1e10
for i3 in range(8, -2, -1):
    v1 *= (2.5e-3 + v1)
    if i3 < 0:
        print((str(abs(v1)) + f'{(v1 / (abs(v1) + 1.0)):>10.1f}-'))
'''

FORMATS = '''\
import math

p = float('nan')
n = math.copysign(float('nan'), -1.0)
mm = 1e308 * 10 % 0.75
inf = 1e308 * 10
for tag, v in (('pos', p), ('neg', n), ('mod', mm), ('div', inf / inf),
               ('inf', inf), ('ninf', -inf), ('nzero', -0.0), ('zero', 0.0)):
    print(tag, f'{v:>10.1f}|{v:.0f}|{v:f}|{v:F}|{v:E}|{v:G}|{v:%}|{v:+f}|{v: 08.2f}')
    print(tag, format(v, '.1f'), format(v, '+08.2f'), '%10.1f' % v, '%+f' % v, str(v), repr(v))
'''

ROUTES = '''\
import math


class S:
    def __init__(self, v):
        self.v = v


def show(label, v):
    print(label, f'{v:>10.1f}', f'{v:.0f}', '%10.1f' % v, str(v), repr(v))


def relay(v):
    show('arg', v)


n = math.copysign(float('nan'), -1.0)
xs = [n, 1.0]
s = S(n)
d = {'n': n}
relay(n)
show('list', xs[0])
show('attr', s.v)
show('dict', d['n'])
'''


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr[-1500:]


def build_and_run(directory, name, text, extra):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_UNIFIED_FORCE', 'AIL_UNIFIED', 'AIL_IR', 'AIL_NO_GENERAL'):
        env.pop(key, None)
    env.update(extra)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True,
                           timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class NanSignFixedPoint(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz246-') as directory:
            want, want_rc, want_err = cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, want_err)
            for mode, extra in MODES:
                got, err = build_and_run(directory, '%s_%s' % (slug, mode), text, extra)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (text, mode, err))
                self.assertEqual(got, (want, want_rc), '%s (%s)\n%s' % (text, mode, err))

    def test_minimized_fuzzer_seed(self):
        self.check('minimized', MINIMIZED)
        with tempfile.TemporaryDirectory(prefix='ail-fz246-') as directory:
            want, _, _ = cpython(directory, 'line', MINIMIZED)
            self.assertIn(b'inf       nan-', want)
            got, err = build_and_run(directory, 'line_default', MINIMIZED, {})
            self.assertIsNotNone(got, err)
            self.assertIn(b'inf       nan-', got[0], err)

    def test_formats_and_other_float_values(self):
        self.check('formats', FORMATS)

    def test_argument_list_attribute_dict(self):
        self.check('routes', ROUTES)


if __name__ == '__main__':
    unittest.main()
