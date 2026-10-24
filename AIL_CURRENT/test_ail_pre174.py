"""pre174: int64-boundary constant expressions are folded exactly, then checked once.

`-(2**E*2)` is INT64_MIN and `2**E+2**E-1` is INT64_MAX for E = 62, even though
the intermediate `2**E*2` is 2**63.  CPython's integers are unbounded, so the
module-constant folder now evaluates the whole expression exactly and checks
only the final value.  The same expressions are folded where the value is used:
as a call argument, a list item, an attribute value and a dict value.  The
general emitters also read the single literal `-9223372036854775808` as INT64_MIN
instead of refusing its positive operand.  Results that do not fit int64 still
stop with `integer overflow`.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BOUNDARY = r'''E = 62
print(-(2**E*2))
print(2**E+2**E-1)
'''

CHANNELS = r'''E = 62
class C:
    def __init__(self):
        self.v = 0
        self.w = 0


def show(v):
    print(v)


show(-(2**E*2))
show(2**E+2**E-1)
print([-(2**E*2), 2**E+2**E-1])
c = C()
c.v = -(2**E*2)
c.w = 2**E+2**E-1
print(c.v, c.w)
d = {"min": -(2**E*2), "max": 2**E+2**E-1}
print(d["min"], d["max"])
print((2**E*2) - (2**E*2) - 1)
print(2**62 * 2 - 1)
'''

ASSIGN = r'''E = 62
A = -(2**E*2)
B = 2**E+2**E-1
print(A, B)
A = 0
B = 0
print(A, B)
'''

FUNCTION_LITERAL = r'''def main():
    print(-(2**62*2))
    print(2**62+2**62-1)
    print(-(2**64 - 2**63))
    print(~(2**63 - 1))


main()
'''

MIN_LITERAL = r'''print(-9223372036854775808)
print([-9223372036854775808])
print({"a": -9223372036854775808})
class C:
    def __init__(self):
        self.v = -9223372036854775808
print(C().v)
def f():
    return -9223372036854775808
print(f())
'''

PURE_LITERAL_MAX = r'''print(2**63 - 1)
print(2**63 - 2**63)
print(-(2**64 - 2**63))
'''

OUT_OF_RANGE = r'''print(2**63)
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


class Pre174Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre174-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_boundary(self):
        self.check('boundary', BOUNDARY)

    def test_channels(self):
        self.check('channels', CHANNELS)

    def test_assigned_and_rebound(self):
        self.check('assigned', ASSIGN)

    def test_function_literal_boundaries(self):
        self.check('function_literal', FUNCTION_LITERAL)

    def test_min_literal_positions(self):
        self.check('min_literal', MIN_LITERAL)

    def test_pure_literal_max_and_exact_intermediates(self):
        self.check('pure_literal', PURE_LITERAL_MAX)

    def test_out_of_range_result_still_stops(self):
        text = OUT_OF_RANGE
        with tempfile.TemporaryDirectory(prefix='ail-pre174-bad-') as directory:
            for general in (True, False):
                got, build_err = _build_and_run(directory, 'out_of_range_%s' % general, text, general)
                self.assertIsNotNone(got, build_err)
                stdout, rc = got
                self.assertEqual(rc, 1, (general, stdout, build_err))
                self.assertEqual(stdout, b'', (general, build_err))
                self.assertIn('integer overflow', build_err, general)


if __name__ == '__main__':
    unittest.main()
