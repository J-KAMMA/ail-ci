"""Pre-90: chr() code points outside the 16-bit v2 runtime.

The general path's v2 runtime stores string units in 16 bits unless the wide
host headers are used.  `chr()` of a constant surrogate or non-BMP code point
used to build and then die with an internal error at run time; the literal
spelling of the same text was already refused by name at compile time.  The
constant calls are now refused the same way, while every BMP value (including
0xFFFF), bool coercion and the range/type errors stay CPython-compatible.  The
runtime store follows the host unit width so a 32-bit build is not truncated.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CHR_BMP = r'''class Box:
    pass


def make(n):
    return chr(n)


def main():
    for n in [0, 1, 31, 32, 65, 126, 127, 128, 255, 256, 0x7FF, 0x800,
              0xD7FF, 0xE000, 0xFFFD, 0xFFFF, True]:
        c = chr(n)
        print(type(n).__name__, n, repr(c), len(c), ord(c))
    b = Box()
    b.v = 67
    d = {"v": 68}
    xs = [69]
    print(make(66), chr(b.v), chr(d["v"]), chr(xs[0]))
    for bad in [-1, 0x110000]:
        try:
            print(chr(bad))
        except ValueError as e:
            print("ValueError", e)
    for bad in [1.5, "x", None, [1]]:
        try:
            print(chr(bad))
        except TypeError as e:
            print("TypeError", e)


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)


class Pre90Tests(unittest.TestCase):
    def test_bmp_chr_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre90-') as directory:
            want, want_rc, err = _cpython(directory, 'bmp', CHR_BMP)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                built = _build(directory, 'bmp_%s' % ('g' if general else 'd'), CHR_BMP, general)
                self.assertEqual(built.returncode, 0,
                                 '%s (general=%s)' % (built.stdout + built.stderr, general))
                exe = Path(directory) / ('exe_bmp_%s' % ('g' if general else 'd'))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
                                 (want, want_rc), 'general=%s' % general)

    def test_non_bmp_constants_are_refused_by_name(self):
        for cp in ('0x10000', '0x1F600', '0x10FFFF'):
            text = 'print(chr(%s))\n' % cp
            with tempfile.TemporaryDirectory(prefix='ail-pre90-') as directory:
                for general in (True, False):
                    built = _build(directory, 'nonbmp_%s' % ('g' if general else 'd'), text, general)
                    message = built.stdout + built.stderr
                    self.assertEqual(built.returncode, 3, message)
                    self.assertIn('not in the subset', message)
                    self.assertIn('non-BMP', message)

    def test_surrogate_constants_are_refused_by_name(self):
        for cp in ('0xD800', '0xDFFF'):
            text = 'print(chr(%s))\n' % cp
            with tempfile.TemporaryDirectory(prefix='ail-pre90-') as directory:
                for general in (True, False):
                    built = _build(directory, 'surrogate_%s' % ('g' if general else 'd'), text, general)
                    message = built.stdout + built.stderr
                    self.assertEqual(built.returncode, 3, message)
                    self.assertIn('not in the subset', message)
                    self.assertIn('surrogate', message)


if __name__ == '__main__':
    unittest.main()
