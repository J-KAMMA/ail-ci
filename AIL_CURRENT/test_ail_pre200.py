"""pre200: a maxsplit intermediate above the old 4096-bit cap is folded exactly.

The pre195 review recorded that ``"a b c".split(" ", 2**4096 // 2**4050)`` (final value
2**46) and ``2**4096 >> 4096`` (final value 1) were still refused by name although CPython
computes them.  The folder's power branch measured the exponent with the old blanket
``right >= 64`` rule and the intermediate width cap was 4096 bits, so a 4097-bit intermediate
was too big even when the whole expression reduces to an int64 value.  Powers are now measured
by their exact width under the folder's limit, so a wider intermediate is accepted as long as
the expression stays inside that limit; the shared int constant folder uses the same limit, so
the same expression also folds when it reaches split through a value.

On this integration tree the accepted pre200 raise to 8192 bits is subsumed by the pre190 fold
limit (2**20 bits, 2**24 for a large exponent), which is kept.  The over-limit cases below
therefore use an intermediate beyond 2**20 bits.  A final value outside int64, or an
intermediate above the fold limit, is still refused by name.  The value reaches split/rsplit as
a literal expression, an argument, a list item, an attribute, a dict value and a local, on both
builds.
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
    n = 2**4096 // 2**4050


def cut(s, sep, n):
    return s.split(sep, n), s.rsplit(sep, n)


def main():
    print("a b c".split(" ", 2**4096 // 2**4050))
    print("a b c".rsplit(" ", 2**4096 // 2**4050))
    print("a b c".split(" ", 2**4096 >> 4096))
    print("a b c".rsplit(" ", 2**4096 >> 4096))
    print("a b c".split(" ", 2**100 // 2**80))
    print("a b c".split(" ", 2**4096 // 2**4095))
    print("a b c".split(" ", (-2)**4096 // 2**4050))
    print("a b c".split(" ", ((2**63 * 4)**63) >> 4095))
    print("a b c".split(" ", 2**8191 // 2**8180))
    xs = [2**4096 // 2**4050]
    d = {"n": 2**4096 // 2**4050}
    n = 2**4096 // 2**4050
    print(cut("a b c", " ", 2**4096 // 2**4050))
    print(cut("a b c", " ", xs[0]))
    print(cut("a b c", " ", Box.n))
    print(cut("a b c", " ", d["n"]))
    print(cut("a b c", " ", n))


main()
'''

OVER_FOLD_LIMIT = [
    ('pow_over_limit', 'print("a b c".split(" ", 2**2000000 // 2**1999990))\n', False),
    ('rshift_over_limit', 'print("a b c".split(" ", 2**2000000 >> 1999990))\n', False),
]

OVER_INT64 = [
    ('direct_over', 'print("a b c".split(" ", 2**63))\n', True),
    ('reduced_over', 'print("a b c".split(" ", 2**100 // 2**80 * 2**70))\n', True),
]

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


class Pre200Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre200-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, want_rc), 'general=%s\n%s' % (general, build_err))

    def check_refused(self, slug, text, cpython_raises):
        with tempfile.TemporaryDirectory(prefix='ail-pre200-') as directory:
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

    def test_wide_intermediate_folded(self):
        self.check('folded', FOLDED)

    def test_intermediate_above_fold_limit_refused(self):
        for slug, text, cpython_raises in OVER_FOLD_LIMIT:
            self.check_refused(slug, text, cpython_raises)

    def test_final_value_outside_int64_refused(self):
        for slug, text, cpython_raises in OVER_INT64:
            self.check_refused(slug, text, cpython_raises)


if __name__ == '__main__':
    unittest.main()
