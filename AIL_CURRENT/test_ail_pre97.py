"""pre97: a constant str.split/rsplit maxsplit is folded, and out-of-int64 is refused.

qtest2's reviewer recorded that a maxsplit constant above int64 stopped the program with
``integer overflow`` where CPython raises ``OverflowError``.  pre70 left that item alone.  A
constant expression is now evaluated exactly when the compiler sees it: a value that fits is
emitted as one literal (so ``2**63 - 1`` does not overflow at the intermediate power), and a
value that does not fit is refused by name on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

IN_RANGE = r'''def main():
    s = "a b c d"
    print(s.split(" ", 2**63 - 1))
    print(s.rsplit(" ", -(2**63)))
    print(s.split(" ", (2**63) // 2))
    print(s.split(" ", 2**62 * 2 - 1))
    print(s.split(" ", -1 << 63))
    print(s.split(" ", 1 << 62))
    print(s.rsplit(" ", 2**63 - 2**63 + 1))
    print(s.split(" ", 2**63 - 2**63 + 5))


main()
'''

DYNAMIC = r'''class Box:
    def __init__(self, n):
        self.n = n


def cut(s, sep, n):
    return s.split(sep, n), s.rsplit(sep, n)


def main():
    xs = [1, -1]
    d = {"n": 2}
    print(cut("a b c", " ", xs[0]))
    print(cut("a b c", " ", d["n"]))
    print(" a  b ".split(None, xs[1]), " a  b ".rsplit(None, Box(0).n))
    print("a,b,c".split(",", 0), "a,b,c".rsplit(",", 1), "a,b,c".split(",", -1))


main()
'''

OUT_OF_RANGE = [
    ('pow_split', 'print("a b c".split(" ", 10**30))\n'),
    ('pow_rsplit', 'print("a b c".rsplit(" ", -10**30))\n'),
    ('pow_none_sep', 'print("a b c".split(None, 10**30))\n'),
    ('pow_keyword', 'print("a b c".split(" ", maxsplit=10**30))\n'),
    ('shift_over', 'print("a b c".split(" ", 1 << 63))\n'),
    ('pow_over', 'print("a b c".split(" ", 2**63))\n'),
]


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


class Pre97Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre97-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def check_refused(self, slug, text, needle):
        with tempfile.TemporaryDirectory(prefix='ail-pre97-') as directory:
            _, got_rc, err = _cpython(directory, slug, text)
            self.assertNotEqual(got_rc, 0, 'CPython was expected to raise:\n%s' % text)
            self.assertIn(b'OverflowError', err, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNone(got, 'built and ran instead of refusing (general=%s):\n%s\n%s'
                                  % (general, text, build_err))
                self.assertIn(needle, build_err, 'general=%s\n%s' % (general, build_err))

    def test_constant_maxsplit_in_range(self):
        self.check('in_range', IN_RANGE)

    def test_dynamic_maxsplit_from_argument_list_attribute_dict(self):
        self.check('dynamic', DYNAMIC)

    def test_constant_maxsplit_above_int64_refused(self):
        for slug, text in OUT_OF_RANGE:
            self.check_refused(slug, text, 'maxsplit constant does not fit in a 64-bit signed integer')

    def test_maxsplit_literal_above_int64_refused(self):
        self.check_refused('literal_over', 'print("a b c".split(" ", 9223372036854775808))\n',
                           'int64 literal out of range')


if __name__ == '__main__':
    unittest.main()
