"""pre54: a constant `round()` at the int64 boundary matches CPython.

`round(x)` with one argument returns an int.  `round(-9223372036854775808.0)` is exactly
INT64_MIN, and `abs()`, unary `-` and `* -1` on it give 2**63.  With exact ints (bigint,
BIGINT.md) the program builds on both builds and prints CPython's answers (it used to be
refused by name while ints were signed 64-bit).  Values just inside the boundary, a
two-argument round() (a float result) and a user-defined `round` keep CPython's answers.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = {
    'direct': '''\
x = round(-9223372036854775808.0)
print(type(x).__name__, x)
print(abs(x))
print(-x)
print(x * -1)
''',
    'container': '''\
xs = [round(-9223372036854775808.0)]
print(abs(xs[0]))
''',
    'attribute': '''\
class Holder:
    def __init__(self, v):
        self.v = v

h = Holder(round(-9223372036854775808.0))
print(h.v * -1)
''',
    'dict_value': '''\
d = {"v": round(-9223372036854775808.0)}
print(-d["v"])
''',
}

NEAR = r'''
class Holder:
    def __init__(self, v):
        self.v = v


def probe(v):
    return abs(v), -v, v * -1


def main():
    boundary = round(-9223372036854774784.0)
    print(boundary, probe(boundary))
    xs = [boundary]
    print(abs(xs[0]), -xs[0], xs[0] * -1)
    h = Holder(boundary)
    print(abs(h.v), -h.v, h.v * -1)
    d = {"v": boundary}
    print(abs(d["v"]), -d["v"], d["v"] * -1)


main()
'''

TWO_ARG = '''\
x = round(-9223372036854775808.0, 0)
print(type(x).__name__, x, abs(x), -x, x * -1)
'''

SHADOWED = '''\
def round(x):
    return x * 2.0


print(type(round(-9223372036854775808.0)).__name__, round(-9223372036854775808.0))
'''


def _compile(directory, name, text, general):
    src = Path(directory) / (name + '.py')
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


class Pre54Tests(unittest.TestCase):
    def test_constant_round_at_the_boundary_matches_cpython(self):
        # exact ints (bigint): builds and matches CPython (stdout, exit code)
        for label, text in REFUSED.items():
            self.check_matches_cpython('boundary_' + label, text)

    def check_matches_cpython(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre54-') as directory:
            src = Path(directory) / (slug + '_cpython.py')
            src.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                                  env=dict(os.environ, PYTHONUTF8='1'))
            self.assertEqual(want.returncode, 0, want.stderr.decode('utf-8', 'replace'))
            for general in (True, False):
                with self.subTest(slug=slug, general=general):
                    built, exe = _compile(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                          text, general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want.stdout.replace(b'\r\n', b'\n'))
                    self.assertEqual(got.returncode, want.returncode, got.stderr[-1500:])

    def test_inside_boundary_through_argument_list_attribute_and_dict(self):
        self.check_matches_cpython('near', NEAR)

    def test_two_argument_round_returns_a_float_and_is_not_refused(self):
        self.check_matches_cpython('two_arg', TWO_ARG)

    def test_user_defined_round_is_not_refused(self):
        self.check_matches_cpython('shadowed', SHADOWED)


if __name__ == '__main__':
    unittest.main()
