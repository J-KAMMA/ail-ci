"""qtest2: str.split/rsplit maxsplit=None must not be read as maxsplit=0.

The general path merged ``maxsplit=`` into the positional slot and then read the
int field of the None object, so ``"a b".split(maxsplit=None)`` printed
``['a b']`` (maxsplit 0) instead of raising the ``TypeError`` CPython raises;
``"a,b,c".rsplit(",", maxsplit=None)`` likewise kept the whole text.  The
literal None is now refused by name.  The whitespace-run, tab/newline,
maxsplit 0/1/-1 and empty-string shapes around it stay compared with CPython on
both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

VALID = r'''class Box:
    def __init__(self, s):
        self.s = s


def cut(s, sep, n):
    return s.split(sep, n), s.rsplit(sep, n)


def cutw(s, n):
    return s.split(None, n), s.rsplit(None, n)


def main():
    for s in ["", " ", "\t\n", "  a   b  ", "a\tb\nc\rd", "\x1ca\x85b\xa0c"]:
        for n in [0, 1, 2, -1, -2]:
            print(repr(s), n, s.split(None, n), s.rsplit(None, n))
    for s in ["", ",", ",a,", "a,,b", "aaa", "aaaa"]:
        for sep in [",", "aa"]:
            for n in [0, 1, 2, -1]:
                print(repr(s), repr(sep), n, s.split(sep, n), s.rsplit(sep, n))
    d = {"s": " a\tb\nc ", "sep": ",", "n": 1}
    xs = [" a  b ", "a,b,c"]
    b = Box("  x  y  ")
    print(cutw(d["s"], d["n"]))
    print(cutw(xs[0], 0))
    print(cut(xs[1], d["sep"], 1))
    print(cutw(b.s, -1))
    print("a,b,c".split(maxsplit=1), "a,b,c".rsplit(maxsplit=1))
    print(" a  b  c ".split(sep=None, maxsplit=0), " a  b  c ".rsplit(sep=None, maxsplit=0))


main()
'''

NONE_SPLIT = r'''def main():
    print("a b".split(maxsplit=None))


main()
'''

NONE_RSPLIT = r'''def main():
    print("a,b,c".rsplit(",", maxsplit=None))


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


class Qtest2Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-qtest2-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def check_refused(self, slug, text, needle):
        with tempfile.TemporaryDirectory(prefix='ail-qtest2-') as directory:
            _, got_rc, err = _cpython(directory, slug, text)
            self.assertNotEqual(got_rc, 0, 'CPython was expected to raise:\n%s' % text)
            self.assertIn(b'TypeError', err, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNone(got, 'built and ran instead of refusing (general=%s):\n%s\n%s'
                                  % (general, text, build_err))
                self.assertIn(needle, build_err, 'general=%s\n%s' % (general, build_err))

    def test_split_rsplit_shapes(self):
        self.check('valid', VALID)

    def test_split_maxsplit_none_refused(self):
        self.check_refused('none_split', NONE_SPLIT, 'split() maxsplit cannot be None')

    def test_rsplit_maxsplit_none_refused(self):
        self.check_refused('none_rsplit', NONE_RSPLIT, 'rsplit() maxsplit cannot be None')


if __name__ == '__main__':
    unittest.main()
