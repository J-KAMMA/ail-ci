"""Pre-existing differences revisited (job pre122).

A non-BMP character used as a format-spec fill cannot exist in the 16-bit general runtime: its
only route there is chr(), which stopped with an uncatchable "requires 32-bit strings" error
instead of the ValueError the format parser would have raised. The general path now refuses a
constant chr() of a non-BMP code point, or of a lone surrogate, by name at compile time. BMP
fills (including non-Latin-1 ones) and every BMP chr() still match CPython, and out-of-range
chr() arguments still raise CPython's ValueError at run time.

The exact cases are compared with CPython on the default build and on the forced general path.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NON_BMP_FILL = '''
print(repr(format("x", chr(0x1F600) + ">5")))
print(repr(f"{'x':{chr(0x1F600)}>5}"))
'''

NON_BMP_VIA_LIST = '''
xs = [chr(0x1F600)]
print(repr(format("x", xs[0] + ">5")))
'''

SURROGATE_CHR = '''
print(repr(chr(0xD800)))
'''

BMP_FILL = '''
class Box:
    def __init__(self, spec):
        self.spec = spec


def fmt(v, spec):
    return format(v, spec)


def main():
    specs = ["日>5", "é^7", "*<4"]
    d = {"s": "日>5"}
    b = Box("é>6")
    print(repr(format("x", specs[0])))
    print(repr(format("x", "日>5")))
    print(repr(format("x", d["s"])))
    print(repr(f"{'ab':{specs[0]}}"))
    print(repr(fmt("ab", specs[2])))
    print(repr(f"{'x':{b.spec}}"))
    print(repr(f"{'':日>3}"))
    print(repr(f"{'abc':日>2}"))
    print(repr(f"{42:日^8d}"))
    print(repr(f"{-42:é>9d}"))
    print(repr(f"{-3.5:日<10.2f}"))
    print(repr(fmt(0, "*^5d")))
    print(repr(fmt(-1, "*^5d")))
    print(repr(fmt("abcdef", "日>8.3")))
    print(repr(fmt("abcdef", "é<8.3")))


main()
'''

CHR_BOUNDARIES = '''
def main():
    for n in (0, 65, 0x263A, 0xD7FF, 0xE000, 0xFFFF):
        c = chr(n)
        print(n, repr(c), len(c), ord(c))
    for n in (-1, 0x110000):
        try:
            print(repr(chr(n)))
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


def _build(directory, name, text, general):
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
    return built, exe


def _run(exe, directory):
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return got.stdout.replace(b'\r\n', b'\n'), got.returncode, got.stderr.decode('utf-8', 'replace')


class Pre122Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre122-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                built, exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-2000:])
                got = _run(exe, directory)
                self.assertEqual(got[:2], (want, want_rc),
                                 '%s (general=%s)\n%s' % (text[:1000], general, got[2][-1500:]))

    def refused(self, slug, text, name):
        with tempfile.TemporaryDirectory(prefix='ail-pre122-') as directory:
            for general in (True, False):
                built, _exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, '%s built (general=%s)' % (slug, general))
                self.assertIn('not in the subset', output, output[-2000:])
                self.assertIn(name, output, output[-2000:])

    def test_non_bmp_format_fill_is_refused_by_name(self):
        self.refused('non_bmp_fill', NON_BMP_FILL, 'chr() of U+1F600 is refused')
        self.refused('non_bmp_via_list', NON_BMP_VIA_LIST, 'chr() of U+1F600 is refused')

    def test_lone_surrogate_chr_is_refused_by_name(self):
        self.refused('surrogate_chr', SURROGATE_CHR, 'chr() of U+D800 is refused')

    def test_bmp_fill_matches_cpython(self):
        self.check('bmp_fill', BMP_FILL)

    def test_chr_boundaries_match_cpython(self):
        self.check('chr_boundaries', CHR_BOUNDARIES)


if __name__ == '__main__':
    unittest.main()
