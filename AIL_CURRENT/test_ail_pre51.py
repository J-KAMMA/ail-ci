"""pre51: format-spec errors and the float 'z' flag match CPython.

The general path's format-spec parser built its own errors.  A space sign on a
str said "Sign not allowed" instead of CPython's "Space not allowed"; an
invalid spec omitted the spec and the value's type; and an unknown format code
printed the raw character instead of CPython's escaped '\\xNN'.  The float 'z'
(negative-zero coercion) flag already formatted correctly and is kept here
together with its width/precision forms.  Each program runs through CPython and
both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SPEC_ERRORS = r'''class Box:
    def __init__(self, v):
        self.v = v


def show(v, s):
    try:
        print(repr(v), repr(s), '->', repr(format(v, s)))
    except Exception as e:
        print(repr(v), repr(s), '!!', type(e).__name__, str(e))


def apply(v, s):
    try:
        return repr(format(v, s))
    except Exception as e:
        return type(e).__name__ + ' ' + str(e)


def main():
    for s in [' 8', ' 8s', ' 8.2s', ' ', ' +8', ' +8s', ' +q', ' 8d', '-8',
              'q', '\x01', '\x80', '\u2603', '', '8', '.2', '>8']:
        show('abc', s)
    for s in [' 8', ' +8', ' 8d', '8 ', '8\x01', '8\x80', '8q', '8\u2603',
              ' ', 'z', 'a\x01b', '+08d', '#x', ',d']:
        show(123, s)
    for s in [' 8', ' +8', '8 ', '8\x01', '8\x80', '8q', '8\u2603', 'z',
              '.2z', '8z', 'z.2f', '+z', 'z#.0f', '<z10.2f', 'z08.2f']:
        show(1.5, s)
    for s in [' 8', ' +8', '8 ', '8q', '8\x80', 'z', 'b', '08x']:
        show(True, s)
    d = {'s': 'xy', 'i': 9}
    box = Box('xz')
    print(apply(d['s'], ' 8'))
    print(apply(box.v, ' +8'))
    print(apply(d['i'], '8 '))
    print(apply(d['i'], '8\x80'))


main()
'''

Z_FLAG = r'''class Box:
    def __init__(self, v):
        self.v = v


def negate(x):
    return -x


def main():
    xs = [-0.0, -1.5, 0.0, 1.5]
    d = {'z': -0.0, 'n': -1.5}
    box = Box(-0.0)
    for spec in ['z', 'z.2f', '+z', 'z08.2f', 'z#.0f', '<z10.2f', 'z.0f', 'z.3e']:
        for v in xs:
            print(repr(v), repr(spec), repr(format(v, spec)))
        print(repr(format(negate(0.0), spec)), repr(format(xs[0], spec)),
              repr(format(box.v, spec)), repr(format(d['z'], spec)))
    for v in [1, 'x']:
        try:
            print(format(v, 'z'))
        except Exception as e:
            print(type(e).__name__, str(e))


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


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
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre51Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre51-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_format_spec_errors(self):
        self.check('spec_errors', SPEC_ERRORS)

    def test_negative_zero_flag(self):
        self.check('z_flag', Z_FLAG)


if __name__ == '__main__':
    unittest.main()
