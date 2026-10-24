"""Pre35 difference 1: round() of a float whose integer result is outside int64.

CPython ints are unbounded, so round(1e300) is a 301-digit int.  The general build keeps
that value as a decimal big integer and prints/compares/adds it exactly.  The direct build
has no boxed integer: a value it cannot know at compile time stops by name at run time,
and a constant that is visibly out of range is refused while compiling.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BIG_LITERALS = r'''print(round(1e300))
print(round(-1e300))
print(round(9.223372036854776e18))
print(round(1e300, 2))
print(round(1e300, 0))
'''

BIG_OPS = r'''big = round(1e300)
print(big + 1)
print(big - 1)
print(big * 4)
print(-big)
print(abs(-big))
print(big == round(1e300))
print(big > 0)
print(big < 0)
print(big == 1e300)
print(1e299 < big)
print(str(big)[:10], len(str(big)))
print(int(big) == big)
print(float(big))
print([big])
print((big,))
print({'k': big})
print(big + big)
print(big - big)
print(big * 0)
'''

BOUNDARIES = r'''print(round(9223372036854774784.0))
print(round(-9223372036854775808.0))
print(round(2.5))
print(round(3.5))
print(round(-2.5))
print(round(0.125, 2))
print(round(2.675, 2))
print(round(-0.4, 0))
'''

REVIEW_FIXES = r'''big = round(1e300)
b1 = big + 1
print(b1 == 1e300, b1 > 1e300, b1 < 1e300)
print(big == 1e300, big < 1e300, big > 1e300)
print(big == float('inf'), big < float('inf'))
huge = big * big
print(huge == float('inf'), huge < float('inf'))
def attempt(label, f):
    try:
        print(label, f())
    except OverflowError as e:
        print(label, type(e).__name__, str(e))
attempt('float', lambda: float(huge))
attempt('add', lambda: huge + 1.0)
attempt('mul', lambda: huge * 1.0)
print(round(big, 2))
print(round(big, -3))
print(round(-big, -3))
print(big // 2, big % 7, -big // 7, -big % 7)
print(big // -7, big % -7, -big // -7, -big % -7)
print(big / 2, big ** 2, big >> 3, -big >> 3, big << 3)
print(big & (big - 1), big | 1, big ^ (big >> 1), ~big)
def show(v):
    print(v + 1 == round(1e300) + 1)
    print(isinstance(v, int))
    print(int(v) == v, hash(v) == hash(1e300))
show(big)
d = {big: 'v'}
print(d[round(1e300)], d[1e300])
print(hash(big), hash(-big))
'''

DYNAMIC = r'''def show(v):
    print(round(v))
show(1e300)
'''

OUTSIDE = 'outside int64'


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.returncode, done.stdout.replace(b'\r\n', b'\n'), done.stderr.decode('utf-8', 'replace')


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
        return None, b'', built.stdout + built.stderr
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.returncode, got.stdout.replace(b'\r\n', b'\n')), got.stderr.decode('utf-8', 'replace'), ''


class Pre35RoundTests(unittest.TestCase):
    def check_both(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre35-') as directory:
            want_rc, want, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, got_err, build_err = _build_and_run(
                    directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want_rc, want), '%s (general=%s)\n%s\n%s'
                                 % (slug, general, got_err, build_err))

    def test_big_literals(self):
        self.check_both('big_literals', BIG_LITERALS)

    def test_big_operations(self):
        self.check_both('big_operations', BIG_OPS)

    def test_boundaries(self):
        self.check_both('boundaries', BOUNDARIES)

    def test_review_fixes(self):
        self.check_both('review_fixes', REVIEW_FIXES)

    def test_dynamic_general_matches(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre35-') as directory:
            want_rc, want, err = _cpython(directory, 'dynamic', DYNAMIC)
            self.assertEqual(want_rc, 0, err)
            got, got_err, build_err = _build_and_run(directory, 'dynamic_g', DYNAMIC, True)
            self.assertIsNotNone(got, build_err)
            self.assertEqual(got, (want_rc, want), got_err)

    def test_dynamic_direct_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre35-') as directory:
            got, got_err, build_err = _build_and_run(directory, 'dynamic_d', DYNAMIC, False)
            if got is None:
                self.assertIn(OUTSIDE, build_err)
                return
            self.assertNotEqual(got[0], 0)
            self.assertEqual(got[1], b'')
            self.assertIn(OUTSIDE, got_err)


if __name__ == '__main__':
    unittest.main()
