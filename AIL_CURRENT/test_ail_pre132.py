"""pre132: the alternate '#' form keeps a decimal point in a type-less float field.

CPython prints `1.e+300` for `format(1e300, '#')` and `format(1e300, '#\\x00')`;
the general formatter and the literal f-string path both printed `1e+300`.  The
same applies to `#.0`, widths, zero padding and grouping.  Each program is built
on both builds and compared with CPython, including values that arrive through an
argument, a list item, an attribute and a dict value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DYNAMIC = r'''def main():
    vals = [1e300, 1.0, 1.5, 1e16, 1e15, 1e-5, 0.0, -0.0, 100.0, 1e100, 1.234e300,
            123456789.0, 1e-300, float('inf'), float('-inf'), float('nan')]
    specs = ['', '#', '#\x00', '#20', '*>#20', '*<#20', '*^#20', '#020', '+#', ' #',
             '#.0', '#.3', '#_', '#,', '.3', '20']
    for v in vals:
        for s in specs:
            print(repr(v), repr(s), repr(format(v, s)))


main()
'''

FSTRING = r'''def main():
    for v in [1e300, 1.0, 1.5, 1e16, 1e15, 1e-5, 0.0, -0.0, 100.0, 1e100, 1.234e300,
              float('inf'), float('-inf'), float('nan')]:
        print(repr(v), f"{v:#}", f"{v:#20}", f"{v:*>#20}", f"{v:*^#20}", f"{v:#020}",
              f"{v:+#}", f"{v:#.0}", f"{v:#.3}", f"{v:}", f"{v:20.3}")


main()
'''

SOURCES = r'''class Box:
    pass


def via_arg(x):
    return format(x, '#')


def via_list(xs):
    return format(xs[0], '#')


def via_attr(o):
    return format(o.v, '#')


def via_dict(d):
    return format(d['v'], '#')


def via_fstring(x, spec):
    return f"{x:{spec}}"


def main():
    box = Box()
    for v in [1e300, -1e300, 1e-5, 0.0]:
        box.v = v
        print(via_arg(v), via_list([v]), via_attr(box), via_dict({'v': v}))
        print(format(v, '#'), format(v, '#\x00'), format(v, '#e'), format(v, '#g'),
              format(v, '#20'), via_fstring(v, '#'))


main()
'''

TYPES_EMPTY = r'''def main():
    for v in [1, 0, -1, 255, True, False]:
        print(repr(v), repr(format(v, '')), repr(format(v, '#')), repr(format(v, '#x')))
    for s in ['', 'x', 'abc']:
        print(repr(s), repr(format(s, '')), repr(format(s, '>5')))
    try:
        print(format('x', '#'))
    except ValueError as e:
        print('ValueError', e)


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


class Pre132Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre132-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_dynamic_specs(self):
        self.check('dynamic_specs', DYNAMIC)

    def test_fstring_literal(self):
        self.check('fstring_literal', FSTRING)

    def test_sources(self):
        self.check('sources', SOURCES)

    def test_types_empty(self):
        self.check('types_empty', TYPES_EMPTY)


if __name__ == '__main__':
    unittest.main()
