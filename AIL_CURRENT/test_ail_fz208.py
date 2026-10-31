"""fz208: fixed-point formatting never shows a NaN's sign.

CPython's `%f` / `format(x, 'f')` prints `nan` for both NaN signs. The small fixed-point
formatter (the default path and the general path's `ail_obj_format`) passed the double
straight to glibc's `snprintf("%.*f")`, which writes a negative NaN as `-nan`; a NaN made by
overflowed float modulo therefore printed `-nan` and `-NAN` where CPython printed `nan` and
`NAN`. Both formatters now pad the word `nan` without a sign. The same value is checked
through an argument, a list item, an attribute and a dict value, and next to infinity and
negative zero.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

MODULO_OVERFLOW = r'''n = 1e308 * 10 % 0.75
print(f'{n:.0f}')
'''

FORMATS = r'''p = float('nan')
n = float('-nan')
inf = 1e308 * 10
mm = inf - inf
for v in (p, n, mm, inf, -inf, -0.0, 0.0):
    print(f'{v:.0f}|{v:f}|{v:.2f}|{v:8.2f}|{v:<8.2f}|{v:^9.1f}|{v:08.2f}|{v:#.0f}')
    print(f'{v:F}|{v:E}|{v:G}|{v:%}|{v}')
    print('%.0f|%f|%.2f|%8.2f|%-8.2f' % (v, v, v, v, v))
'''

VALUES = r'''class S:
    def __init__(self, v):
        self.v = v


def make():
    return 1e308 * 10 % 0.75


def show(v):
    print(f'{v:.0f}|{v:f}|{v:8.2f}|{v:08.2f}|{v:^9.1f}')


def relay(v):
    show(v)


n = make()
s = S(n)
xs = [n, 1.0]
d = {'n': n}
relay(n)
show(s.v)
show(xs[0])
show(d['n'])
'''


SIGNS = r'''class S:
    def __init__(self, v):
        self.v = v


def mk():
    return 1e308 * 10 % 0.75


def show(tag, v):
    print(tag, f'{v:+f}|{v: f}|{v:+08.2f}|{v: 08.2f}|{v:+8.2f}|{v: 8.2f}')
    print(tag, f'{v:+<8.2f}|{v:+^9.2f}|{v:+>8.2f}|{v:*>8.2f}|{v:0=8.2f}')
    print(tag, format(v, '+f'), format(v, ' f'), format(v, '+08.2f'), format(v, ' 08.2f'),
          format(v, '+8.2f'), format(v, ' 8.2f'))
    print(tag, '%+f|% f|%+08.2f|% 08.2f|%+8.2f|% 8.2f' % (v, v, v, v, v, v))


p = float('nan')
n = float('-nan')
mi = 1e308 * 10
for tag, v in (('pos', p), ('neg', n), ('mm', mi - mi), ('inf', mi), ('ninf', -mi),
               ('n0', -0.0), ('z', 0.0)):
    show(tag, v)
v = mk()
s = S(v)
xs = [v, 1.0]
d = {'n': v}
show('arg', v)
show('list', xs[0])
show('attr', s.v)
show('dict', d['n'])
'''

MODES = (
    ('default', {}),
    ('general', {'AIL_UNIFIED_FORCE': '1'}),
    ('typed_legacy', {'AIL_IR': '0'}),
    ('general_legacy', {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '0'}),
)


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


class NanFixedFormat(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz208-') as directory:
            want, want_rc, want_err = cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, want_err)
            for mode, extra in MODES:
                got, err = build_and_run(directory, '%s_%s' % (slug, mode), text, extra)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (text, mode, err))
                self.assertEqual(got, (want, want_rc), '%s (%s)\n%s' % (text, mode, err))

    def test_overflowed_modulo(self):
        self.check('modulo_overflow', MODULO_OVERFLOW)

    def test_signs_widths_and_other_types(self):
        self.check('formats', FORMATS)

    def test_argument_list_attribute_dict(self):
        self.check('values', VALUES)

    def test_explicit_sign_flags(self):
        self.check('signs', SIGNS)


if __name__ == '__main__':
    unittest.main()
