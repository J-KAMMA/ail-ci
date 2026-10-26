"""Pre-275: a statically known ``int(<float>)`` outside int64 is refused by name.

AIL integers are fixed width.  ``int(1e300)``, and the same value reached through a defaulted
parameter, a module or local constant, an alias, a list/tuple/dict literal item, a class
attribute or an argument, used to compile on both builds and then stop at run time with
``integer overflow``, while CPython prints the bignum.  A finite float at or above 2**63 or
below -2**63 is now refused before C is emitted with ``int64 constant expression out of
range``.  In-range floats, NaN/infinity, non-float arguments, a default that a call overrides
and a default the body never converts still match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OUT_OF_RANGE = {
    'default': '''def take(x=1e300):
    print(int(x))


take()
''',
    'default_expression': '''def take(x=int(1e300)):
    print(x)


take()
''',
    'keyword_default': '''def take(*, x=1e300):
    print(int(x))


take()
''',
    'literal': '''print(int(1e300))
''',
    'negative': '''print(int(-1e300))
''',
    'high_boundary': '''print(int(9223372036854775807.0))
''',
    'low_boundary': '''print(int(-9223372036854777856.0))
''',
    'expression': '''print(int(1e300 + 1e300))
''',
    'module_constant': '''V = 1e300


def main():
    print(int(V))


main()
''',
    'local_constant': '''def main():
    v = 1e300
    print(int(v))


main()
''',
    'alias': '''V = 1e300
W = V


def main():
    print(int(W))


main()
''',
    'argument': '''def show(value):
    print(value)


def main():
    show(int(1e300))


main()
''',
    'list_item': '''print(int([1e300][0]))
''',
    'attribute': '''class Box:
    v = 1e300


def main():
    print(int(Box.v))


main()
''',
    'dict_value': '''print(int({"v": 1e300}["v"]))
''',
}

IN_RANGE = '''def main():
    print(int(1.5), int(-1.5), int(0.0), int(-0.0), int(True), int(2**62))
    print(int(1e18), int(9223372036854774784.0), int(-9223372036854775808.0))
    print(int(1e-300))


main()
'''

OVERRIDDEN_DEFAULT = '''def take(x=1e300):
    print(int(x))


take(1.5)
take(2.5)
'''

UNUSED_DEFAULT = '''def take(x=1e300):
    print(x)


take()
'''

NON_FLOAT = '''def main():
    print(int("123"), int(1), int(-2**62), int(-2**62.0))


main()
'''

NAN = '''print(int(float("nan")))
'''

INFINITY = '''print(int(float("inf")))
'''

DICT_LAST_VALUE = '''print(int({"v": 1e300, "v": 1.0}["v"]))
'''

DICT_MIXED_KEYS = '''print(int({1: 1e300, 1.0: 2.0}[1]))
print(int({1.0: 1e300, 1: 2.0}[1.0]))
print(int({True: 1e300, 1.0: 2.0}[True]))
K = 1.0
print(int({1: 1e300, K: 2.0}[1]))
V = 1e300
print(int({1: V, 1.0: 2.0}[1]))
print(int({0: 1e300, False: 2.0}[0]))
'''

DICT_DYNAMIC_KEY = '''def f(K):
    print(int({1: 1e300, K: 2.0}[1]))


f(1.0)

extra = {1.0: 1e300}
print(int({**extra, 1: 2.0}[1]))
'''

SHADOWED_ATTRIBUTE = '''class Box:
    v = 1e300


class Other:
    v = 1.0


def by_parameter(Box):
    print(int(Box.v))


def by_local():
    Box = Other
    print(int(Box.v))


def by_lambda():
    f = lambda Box: int(Box.v)
    print(f(Other))


def outer(Box):
    def inner():
        print(int(Box.v))

    inner()


by_parameter(Other)
by_local()
by_lambda()
outer(Other)
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


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre275Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre275-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn('int64 constant expression out of range', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertNotIn('integer overflow', output, '%s (general=%s)' % (slug, general))
                self.assertNotIn('Traceback', output, '%s (general=%s)' % (slug, general))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre275-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc),
                                 '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_constant_float_out_of_int64_is_refused(self):
        for slug, text in OUT_OF_RANGE.items():
            self.refused(slug, text)

    def test_high_boundary_names_the_exact_value(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre275-') as directory:
            built, _ = _build(directory, 'boundary_g', OUT_OF_RANGE['high_boundary'], True)
            self.assertIn('9223372036854775808', built.stdout + built.stderr)

    def test_in_range_floats_and_ints_match_cpython(self):
        self.matches('in_range', IN_RANGE)

    def test_overridden_default_matches_cpython(self):
        self.matches('overridden_default', OVERRIDDEN_DEFAULT)

    def test_default_the_body_does_not_convert_matches_cpython(self):
        self.matches('unused_default', UNUSED_DEFAULT)

    def test_non_float_arguments_match_cpython(self):
        self.matches('non_float', NON_FLOAT)

    def test_nan_and_infinity_keep_their_exceptions(self):
        self.matches('nan', NAN)
        self.matches('infinity', INFINITY)

    def test_duplicate_dict_key_keeps_the_last_value(self):
        self.matches('dict_last_value', DICT_LAST_VALUE)

    def test_equal_dict_keys_of_different_numeric_types_keep_the_last_value(self):
        self.matches('dict_mixed_keys', DICT_MIXED_KEYS)

    def test_dict_with_a_dynamic_key_is_not_folded(self):
        self.matches('dict_dynamic_key', DICT_DYNAMIC_KEY)

    def test_shadowed_class_attribute_is_not_folded(self):
        self.matches('shadowed_attribute', SHADOWED_ATTRIBUTE)


if __name__ == '__main__':
    unittest.main()
