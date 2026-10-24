"""pre36: a non-BMP constant in chr() is refused by name on the general path.

The general (boxed) path stores str as 16-bit units, so ail_bi_chr used to die with
"AIL internal error: chr() non-BMP code point requires 32-bit strings" at run time.
CPython returns a one-character str.  A constant argument in U+10000..U+10FFFF is
now refused while compiling the general path, by name, instead of reaching that
runtime fatal.  The default (typed) build still produces CPython's character, and
BMP boundaries, negative arguments and arguments above U+10FFFF are unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', CLI, 'compile', src.name, '--syntax', 'python',
                           '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900,
                          env=env), exe


def run(exe, directory):
    done = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


class Pre36Tests(unittest.TestCase):
    def test_non_bmp_chr_constant_is_refused_by_name_on_the_general_path(self):
        for code in (0x10000, 0x1F600, 0x10FFFF):
            with tempfile.TemporaryDirectory(prefix='ail-pre36-') as directory:
                built, exe = build(directory, 'non_bmp_%x' % code, 'print(chr(0x%X))\n' % code, True)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, output)
                self.assertFalse(exe.exists(), output)
                self.assertIn('non-BMP code point U+%04X' % code, output)
                self.assertNotIn('Traceback', output)
                self.assertNotIn('AIL internal error', output)

    def test_non_bmp_chr_constant_expressions_are_refused_on_the_general_path(self):
        for text, code in (('print(chr(+0x1F600))\n', 0x1F600),
                           ('print(chr(0xFFFF + 1))\n', 0x10000),
                           ('print(chr(0x8000 * 2))\n', 0x10000)):
            with tempfile.TemporaryDirectory(prefix='ail-pre36-') as directory:
                built, exe = build(directory, 'non_bmp_expr_%x' % code, text, True)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, output)
                self.assertFalse(exe.exists(), output)
                self.assertIn('non-BMP code point U+%04X' % code, output)
                self.assertNotIn('AIL internal error', output)

    def test_bmp_chr_boundaries_still_match_cpython(self):
        text = 'for n in (0, 1, 0x7f, 0x80, 0xff, 0x3a9, 0xffff):\n    print(n, chr(n))\n'
        with tempfile.TemporaryDirectory(prefix='ail-pre36-') as directory:
            want, rc, err = cpython(directory, 'bmp', text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                built, exe = build(directory, 'bmp_%s' % ('g' if general else 'd'), text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertEqual(run(exe, directory), (want, rc))

    def test_out_of_range_chr_still_matches_cpython(self):
        text = ('for n in (-1, -0x10000, 0x110000):\n'
                '    try:\n'
                '        print(chr(n))\n'
                '    except ValueError as e:\n'
                '        print("ValueError", e)\n')
        with tempfile.TemporaryDirectory(prefix='ail-pre36-') as directory:
            want, rc, err = cpython(directory, 'range', text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                built, exe = build(directory, 'range_%s' % ('g' if general else 'd'), text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertEqual(run(exe, directory), (want, rc))

    def test_default_build_keeps_non_bmp_chr(self):
        text = ('print(chr(0x10000))\n'
                'print(chr(0x1F600))\n'
                'print(chr(0x10FFFF))\n'
                'print(len(chr(0x1F600)), ord(chr(0x1F600)))\n')
        with tempfile.TemporaryDirectory(prefix='ail-pre36-') as directory:
            want, rc, err = cpython(directory, 'default', text)
            self.assertEqual(rc, 0, err)
            built, exe = build(directory, 'default_d', text, False)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual(run(exe, directory), (want, rc))


if __name__ == '__main__':
    unittest.main()
