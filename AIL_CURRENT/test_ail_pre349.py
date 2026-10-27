"""A wide constant exponent passed through a user function is refused by name.

The pre330 reviewer recorded as pre-existing that a ``pow()`` wrapper called with a wide
constant exponent (``def power(b, e): return pow(b, e)`` called with ``2`` and
``(3**100) >> 150``) ran on both builds and then stopped with ``integer overflow``, where
CPython prints the bignum.  The pow check now follows constant arguments through a module-level
wrapper, including a keyword call, a default, an alias of ``pow``, a chain of wrappers, and a
value held in a module list or dict or a class attribute.  A wrapper's own scalar, list and
dict assignments win over the caller and module values, a ``global`` mutation before the call
is seen, and a nested ``def`` shadows a wrapper name.  In-range and safe powers, negative
exponents, bool and float operands, an unused wrapper and a shadowed wrapper name still match
CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = {
    'arguments': '''
def power(b, e):
    return pow(b, e)
print(power(2, (3**100) >> 150))
''',
    'base_argument': '''
def power(b):
    return pow(b, (3**100) >> 150)
print(power(2))
''',
    'keyword': '''
def power(b, e):
    return pow(b, e)
print(power(e=(3**100) >> 150, b=2))
''',
    'default': '''
def power(e, b=2):
    return pow(b, e)
print(power((3**100) >> 150))
''',
    'chain': '''
def inner(b, e):
    return pow(b, e)
def outer(b, e):
    return inner(b, e)
print(outer(2, (3**100) >> 150))
''',
    'list_item': '''
def power(b, e):
    return pow(b, e)
vals = [2, (3**100) >> 150]
print(power(vals[0], vals[1]))
''',
    'list_literal_item': '''
def power(b, e):
    return pow(b, e)
print(power([2, (3**100) >> 150][0], [2, (3**100) >> 150][1]))
''',
    'dict_value': '''
def power(b, e):
    return pow(b, e)
d = {"b": 2, "e": (3**100) >> 150}
print(power(d["b"], d["e"]))
''',
    'attribute': '''
class Box:
    b = 2
    e = 361
def power(b, e):
    return pow(b, e)
print(power(Box.b, Box.e))
''',
    'local_alias': '''
def power(b, e):
    p = pow
    return p(b, e)
print(power(2, (3**100) >> 150))
''',
    'negative_base': '''
def power(b, e):
    return pow(b, e)
print(power(-2, 64))
''',
    'other_base': '''
def power(b, e):
    return pow(b, e)
print(power(3, 40))
''',
    'local_wide_shadow': '''
A = 2
E = 10
def power(x):
    A = 3
    E = 40
    return pow(A, E)
print(power(0))
''',
    'parameter_reassignment_wide': '''
def power(b, e):
    e = 63
    return pow(b, e)
print(power(2, 0), power(-2, 0))
''',
}

MATCH = {
    'in_range': '''
def power(b, e):
    return pow(b, e)
print(power(2, 10), power(3, 39), power(-2, 63), power(2, 62))
''',
    'safe_bases': '''
def power(b, e):
    return pow(b, e)
print(power(0, (3**100) >> 150), power(1, (3**100) >> 150),
      power(-1, (3**100) >> 150), power(-1, (3**100) >> 149))
''',
    'negative_exponent': '''
def power(b, e):
    return pow(b, e)
print(power(2, -3), power(-2, -3), power(2.0, -1))
''',
    'types': '''
def power(b, e):
    return pow(b, e)
print(power(True, 5), power(2, True), power(2.0, 3), power(2, 0.5))
''',
    'chain_in_range': '''
def inner(b, e):
    return pow(b, e)
def outer(b, e):
    return inner(b, e)
print(outer(2, 10))
''',
    'shadowed': '''
def power(b, e):
    return pow(b, e)
def main():
    power = lambda b, e: b + e
    print(power(2, 3))
main()
''',
    'in_range_variable': '''
def power(b, e):
    return pow(b, e)
x = 10
print(power(2, x))
''',
    'unused': '''
def power(b, e):
    return pow(b, e)
print(7)
''',
    'huge_negative': '''
def power(b, e):
    return pow(b, e)
print(power(2, -((3**100) >> 150)))
''',
    'local_constant_shadow': '''
e = 40
def power(b, x):
    e = 10
    return pow(b, e)
print(power(3, 0))
''',
    'local_constant_shadow_both': '''
A = 3
E = 40
def power(x):
    A = 2
    E = 10
    return pow(A, E)
print(power(0))
''',
    'global_reset_before_call': '''
E = (3**100) >> 150
def power(b, e):
    return pow(b, e)
def reset():
    global E
    E = 10
reset()
print(power(2, E))
''',
    'nested_def_shadow': '''
def inner(b, e):
    return pow(b, e)
def outer(b, e):
    def inner(b, e):
        return 7
    return inner(b, e)
print(outer(2, (3**100) >> 150))
''',
    'nested_def_shadow_in_range': '''
def inner(b, e):
    return pow(b, e)
def outer(b, e):
    def inner(b, e):
        return b + e
    return inner(b, e)
print(outer(2, 10))
''',
    'local_list_shadow': '''
vals = [2, 40]
def power(b, x):
    vals = [2, 10]
    return pow(vals[0], vals[1])
print(power(0, 0))
''',
    'local_dict_shadow': '''
d = {"b": 2, "e": 40}
def power(b, x):
    d = {"b": 2, "e": 10}
    return pow(d["b"], d["e"])
print(power(0, 0))
''',
    'parameter_reassignment_safe': '''
def power(b, e):
    e = 10
    return pow(b, e)
print(power(3, 40))
''',
    'parameter_reassignment_after_call': '''
def power(b, e):
    r = pow(b, e)
    e = 100
    return r
print(power(2, 10))
''',
}

REFUSAL = 'int64 constant expression out of range'


def build_run(directory, name, source, general):
    src = Path(directory) / (name + '.py')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    src.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            src.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return built.returncode, b'', built.stdout + built.stderr, exe.exists()
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return ran.returncode, ran.stdout.replace(b'\r\n', b'\n'), built.stdout + built.stderr, exe.exists()


class Pre349(unittest.TestCase):
    def test_wide_wrapper_exponent_is_refused_by_name(self):
        for slug, source in REFUSED.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre349-') as directory:
                for general in (False, True):
                    with self.subTest(slug=slug, general=general):
                        status, _, output, exists = build_run(directory, 'pre349_' + slug,
                                                              source, general)
                        self.assertNotEqual(status, 0, output)
                        self.assertFalse(exists, 'built an executable: %s' % output[-2000:])
                        self.assertIn(REFUSAL, output)
                        self.assertNotIn('integer overflow', output)

    def test_in_range_wrapper_powers_match_cpython(self):
        for slug, source in MATCH.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre349-') as directory:
                want = subprocess.run([sys.executable, '-B', '-c', source],
                                      capture_output=True, timeout=60)
                self.assertEqual(want.returncode, 0, want.stderr)
                for general in (False, True):
                    with self.subTest(slug=slug, general=general):
                        status, got, output, _ = build_run(directory, 'pre349_' + slug,
                                                           source, general)
                        self.assertEqual(status, 0, output)
                        self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)


if __name__ == '__main__':
    unittest.main()
