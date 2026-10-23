"""Differential pre20 round: chr() of a non-BMP code point on the general path.

The general (boxed) runtime stores UTF-16 code units, so it cannot represent a code point
above U+FFFF.  `chr(0x1F600)` used to stop with
`AIL internal error: chr() non-BMP code point requires 32-bit strings` on both builds when
the program had no typed entry point.

A literal argument is now refused at build time by name, and a value that only becomes
known at run time stops with the named limit `chr_non_bmp` instead of an internal error.
The typed/default path already represents these characters and still matches CPython.
This round also keeps the BMP boundary and chr()'s range errors on both paths.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NON_BMP_LITERAL = r'''def main() -> None:
    print(chr(0x1F600))


main()
'''

NON_BMP_DYNAMIC = r'''class Box:
    def __init__(self, v: int) -> None:
        self.v: int = v


def show(n: int) -> None:
    print(chr(n), len(chr(n)))


def main() -> None:
    show(0x1F600)
    xs: list[int] = [0x1F600]
    print(chr(xs[0]))
    b: Box = Box(0x1F600)
    print(chr(b.v))
    d: dict[str, int] = {"v": 0x1F600}
    print(chr(d["v"]))


main()
'''

BMP_AND_ERRORS = r'''class Box:
    def __init__(self, v: int) -> None:
        self.v: int = v


def show(n: int) -> None:
    s: str = chr(n)
    print(n, s, len(s), ord(s))


def main() -> None:
    vals: list[int] = [0, 65, 0xD7FF, 0xE000, 0xFFFD, 0xFFFF]
    for n in vals:
        show(n)
    xs: list[int] = [0xFFFF]
    b: Box = Box(0xE000)
    d: dict[str, int] = {"v": 0xD7FF}
    print(chr(xs[0]), chr(b.v), chr(d["v"]))
    for n in [-1, 0x110000]:
        try:
            print(chr(n))
        except ValueError as e:
            print("ValueError", e)


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


class Pre20Tests(unittest.TestCase):
    def check_matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre20-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, detail = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                             text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, detail))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, detail))

    def test_non_bmp_literal_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre20-') as directory:
            got, detail = _build_and_run(directory, 'nonbmp_literal_g', NON_BMP_LITERAL, True)
            self.assertIsNone(got, detail)
            self.assertIn('chr() of the non-BMP code point U+1F600', detail)
            want, rc, err = _cpython(directory, 'nonbmp_literal', NON_BMP_LITERAL)
            self.assertEqual(rc, 0, err)
            got, detail = _build_and_run(directory, 'nonbmp_literal_d', NON_BMP_LITERAL, False)
            self.assertIsNotNone(got, detail)
            self.assertEqual(got, (want, rc), detail)

    def test_non_bmp_runtime_value_hits_named_limit(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre20-') as directory:
            got, detail = _build_and_run(directory, 'nonbmp_dynamic_g', NON_BMP_DYNAMIC, True)
            self.assertIsNotNone(got, detail)
            self.assertEqual(got[1], 3, detail)
            self.assertEqual(got[0], b'', detail)
            self.assertIn('AIL limit: chr_non_bmp', detail)
            want, rc, err = _cpython(directory, 'nonbmp_dynamic', NON_BMP_DYNAMIC)
            self.assertEqual(rc, 0, err)
            got, detail = _build_and_run(directory, 'nonbmp_dynamic_d', NON_BMP_DYNAMIC, False)
            self.assertIsNotNone(got, detail)
            self.assertEqual(got, (want, rc), detail)

    def test_bmp_boundary_and_range_errors_match(self):
        self.check_matches('bmp_errors', BMP_AND_ERRORS)


if __name__ == '__main__':
    unittest.main()
