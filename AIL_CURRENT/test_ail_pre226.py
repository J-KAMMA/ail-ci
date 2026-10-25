"""Pre-226: space-sign zero padding in a general-path f-string field.

The review of job pre206 listed `format(42, ' 05d')` giving `00 42` as a pre-existing
difference (it reproduces through the general path's core f-string formatter, which
`ail_obj_format`/`ail__pad` run; direct `format()` and `str.format()` already match).
CPython's `=` padding puts the zero fill after the sign, and the space sign is a sign
just like `-` and `+`.  `ail__pad` only recognised `-`/`+`, so the zeros went before the
space.  The cases below cover int/bool/float, positive/negative/zero/-0.0, widths around
the sign, the `+`/`-` controls, a type-less int, dynamic nested specs, direct `format()`
and `str.format()` controls, and the value reaching the field through an argument, a list
item, an attribute, a dict value and an alias, on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''class Box:
    def __init__(self, v, s):
        self.v = v
        self.s = s


def one(v):
    return f'{v: 05d}'


def fl(x):
    return f'{x: 09.3f}'


def with_spec(v, s):
    return f'{v:{s}}'


def main():
    for v in (7, 42, -7, -42, 0, True, False):
        print(repr(f'{v: 00d}'), repr(f'{v: 01d}'), repr(f'{v: 02d}'), repr(f'{v: 03d}'))
        print(repr(f'{v: 04d}'), repr(f'{v: 05d}'), repr(f'{v: 06d}'), repr(f'{v: 08d}'))
    print(repr(f'{7: 05}'), repr(f'{42: 08}'))
    print(repr(f'{7:+05d}'), repr(f'{7:-05d}'), repr(f'{7:05d}'), repr(f'{-7:+05d}'))
    print(repr(f'{7: 5d}'))
    for x in (2.5, -2.5, 0.0, -0.0):
        print(repr(f'{x: 09.3f}'), repr(f'{x: 08.2f}'), repr(f'{x: 04.2f}'))
    print(repr(f'{2.5:+010.2f}'), repr(f'{2.5:-010.2f}'))
    print(repr(one(42)), repr(one(-42)), repr(one(0)), repr(one(True)))
    print(repr(fl(2.5)), repr(fl(-2.5)), repr(fl(-0.0)))
    xs = [42, -42, 0]
    for v in xs:
        print(repr(f'{v: 05d}'))
    b = Box(42, ' 05d')
    print(repr(f'{b.v: 05d}'))
    d = {'v': -42, 's': ' 05d'}
    print(repr(f'{d["v"]: 05d}'))
    alias = 0
    print(repr(f'{alias: 05d}'))
    print(repr(with_spec(42, b.s)), repr(with_spec(-42, d['s'])), repr(with_spec(7, ' 08d')))
    print(repr(format(42, ' 05d')), repr(format(-42, ' 05d')), repr(format(0, ' 05d')))
    print(repr(format(2.5, ' 09.3f')), repr(format(-0.0, ' 09.3f')))
    print(repr('{0: 05d}'.format(42)), repr('{0: 09.3f}'.format(-2.5)))
    print(repr('%05d' % 42), repr('% 05d' % 42), repr('% 09.3f' % -2.5))


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
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre226Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre226-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_space_sign_zero_padding(self):
        self.check('space_zero', PROGRAM)
