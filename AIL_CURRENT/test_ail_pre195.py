"""pre195: a maxsplit power below the fold limit is not refused for its exponent.

pre97's maxsplit folder refused every power whose exponent was at least 64 before it looked at
the rest of the expression, so ``"a b c".split(" ", 2**100 // 2**80)`` (final value 2**20) was
refused although the value fits int64.  The power is now bounded by the folder's own 4096-bit
size limit, the same rule the compiler's other constant folder uses, so an intermediate may be
wider than int64 as long as the whole expression folds exactly.  The power guard measures the
actual result width, not `bit_length(base) * exponent`, so `((2**63 * 4)**63) >> 4095` (a
4096-bit intermediate that reduces to 1) is accepted.  A final value outside int64, or an
intermediate wider than 4096 bits, is still refused by name on both builds.  The value reaches
split/rsplit as a literal expression, an argument, a list item, an attribute, a dict value and a
local.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

FOLDED = r'''class Box:
    n = 2**100 // 2**80


def cut(s, sep, n):
    return s.split(sep, n), s.rsplit(sep, n)


def main():
    print("a b c".split(" ", 2**100 // 2**80))
    print("a b c".split(" ", 2**100 // 2**79))
    print("a b c".rsplit(" ", 2**200 // 2**180))
    print("a b c".split(" ", 3**50 // 3**30))
    print("a b c".split(" ", 2**64 // 2**4))
    print("a b c".split(" ", 2**100 >> 80))
    print("a b c".split(" ", (-2)**101 // (-2)**81))
    print("a b c".split(" ", (-2)**101 // (-2)**80))
    print("a b c".split(" ", 2**2048 // 2**2028))
    print("a b c".split(" ", 2**2049 // 2**2029))
    print("a b c".split(" ", 2**4095 // 2**4050))
    print("a b c".split(" ", 2**4095 >> 4050))
    print("a b c".split(" ", ((2**63 * 4)**63) >> 4095))
    print("a b c".split(" ", (2**63)**65 >> 4095))
    print("a b c".split(" ", 2**100 // 2**100))
    xs = [2**100 // 2**80]
    d = {"n": 2**100 // 2**80}
    n = 2**100 // 2**80
    print(cut("a b c", " ", 2**100 // 2**80))
    print(cut("a b c", " ", xs[0]))
    print(cut("a b c", " ", Box.n))
    print(cut("a b c", " ", d["n"]))
    print(cut("a b c", " ", n))


main()
'''

OUT_OF_RANGE = [
    ('direct_over', 'print("a b c".split(" ", 2**100))\n'),
    ('reduced_over', 'print("a b c".split(" ", 2**100 // 2**80 * 2**70))\n'),
]
OVER_FOLD_LIMIT = 'print("a b c".split(" ", 2**4096 // 2**4050))\n'
NEEDLE = 'maxsplit constant does not fit in a 64-bit signed integer'


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


class Pre195Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre195-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, want_rc), 'general=%s\n%s' % (general, build_err))

    def check_refused(self, slug, text, cpython_raises=True):
        with tempfile.TemporaryDirectory(prefix='ail-pre195-') as directory:
            _, got_rc, err = _cpython(directory, slug, text)
            if cpython_raises:
                self.assertNotEqual(got_rc, 0, 'CPython was expected to raise:\n%s' % text)
                self.assertIn(b'OverflowError', err, err)
            else:
                self.assertEqual(got_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNone(got, 'built and ran instead of refusing (general=%s):\n%s\n%s'
                                  % (general, text, build_err))
                self.assertIn(NEEDLE, build_err, 'general=%s\n%s' % (general, build_err))

    def test_power_folded_before_rejection(self):
        self.check('folded', FOLDED)

    def test_out_of_range_still_refused(self):
        for slug, text in OUT_OF_RANGE:
            self.check_refused(slug, text)

    def test_intermediate_above_fold_limit_refused(self):
        self.check_refused('over_fold_limit', OVER_FOLD_LIMIT, cpython_raises=False)


if __name__ == '__main__':
    unittest.main()
