"""Pre-18: a sign flag on a str names CPython's exact ValueError.

CPython rejects every sign flag in a str format spec: a space flag with
"Space not allowed in string format specifier", and `+`/`-` with "Sign not
allowed in string format specifier".  The general path used to report the
space flag as a sign and the core's str formatter silently accepted a sign
altogether.  This module keeps the recorded case (`format('x', ' z')`) and the
other boundaries compared with CPython on both builds: literal and computed
specs, widths and alignment, empty/non-ASCII values, values reaching format
through an argument, a list item, an attribute and a dict value, and numeric
values whose sign flags stay valid.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SIGN_SPECS = r'''class Box:
    pass


def fmt(v, spec):
    try:
        return format(v, spec)
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def main():
    for spec in [' z', ' ', '+', '-', '+5', ' 5', '<+5', '> 4', '^+3', ' z#']:
        print('s', repr(spec), fmt('x', spec))
    for v in ['', 'abc', 'h\u00e9llo']:
        for spec in [' ', ' 3', '+3', '-']:
            print('v', repr(v), repr(spec), fmt(v, spec))
    b = Box()
    b.s = ' abc'
    b.v = '\u00e9'
    specs = [' ', '+6', ' 6']
    d = {'s': ' ', 'v': 'x'}
    print('arg', fmt('q', ' '))
    print('list', fmt('q', specs[0]), fmt('q', specs[1]))
    print('attr', fmt(b.s, specs[2]), fmt(b.v, ' '))
    print('dict', fmt(d['v'], d['s']))
    for v in [0, -7, True]:
        print('i', repr(v), fmt(v, ' '), fmt(v, ' 5'), fmt(v, '+5'))
    for v in [0.0, -0.0, 1.5, -2.25, float('inf'), float('nan')]:
        print('f', repr(v), fmt(v, ' '), fmt(v, ' 8.2f'), fmt(v, '+8.2f'))
    for spec in ['', '5', '<5', '>5', '^5', '.2', '5.2', '*>5', '0>5']:
        print('plain', repr(spec), repr(format('abc', spec)))


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


class Pre18Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre18-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_sign_flag_on_str(self):
        self.check('sign_specs', SIGN_SPECS)


if __name__ == '__main__':
    unittest.main()
