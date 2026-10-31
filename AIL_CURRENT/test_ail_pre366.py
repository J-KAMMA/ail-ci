"""pre366: an aliased power or int() wrapper is followed by the constant checks.

The pre349 reviewer recorded ``r12``: a wrapper called through ``q = power`` still compiled
and then stopped with ``integer overflow`` on both builds, where CPython keeps its exact
unbounded result.  The static checks follow a module-level alias to a wrapper that returns
``base ** exponent`` or ``pow(base, exponent)``, and an alias to an ``int()`` wrapper.

An unsafe call site is either refused by name (constant operands outside int64, an aliased
wrapper whose operands are not known, ``int()`` of a float outside int64) or, on a build
whose general path carries exact big integers (the integration branch's bigint work), it
builds and must print CPython's exact result.  A run-time ``integer overflow`` is never
accepted.  Safe constants and direct wrapper calls must match CPython on every build.

Both the general path and the default build are checked.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OVERFLOW = 'int64 constant expression out of range'
INT_FLOAT = 'int() of a float outside int64'
ALIASED = 'an aliased integer power wrapper called with operands not known'


def compile_source(directory, name, source, general=False):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre366(unittest.TestCase):
    UNSAFE = (
        ('exp_alias', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q(10, 40))
''', OVERFLOW),
        ('pow_alias', '''
def power(base, exponent):
    return pow(base, exponent)
q = power
print(q(2, 63))
''', OVERFLOW),
        ('negative_base', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q(-10, 40))
''', OVERFLOW),
        ('alias_chain', '''
def power(base, exponent):
    return base ** exponent
q = power
r = q
print(r(2, 63))
''', OVERFLOW),
        ('module_constants', '''
def power(base, exponent):
    return pow(base, exponent)
BASE = 2
EXP = 63
q = power
print(q(BASE, EXP))
''', OVERFLOW),
        ('argument', '''
def power(base, exponent):
    return base ** exponent
def run(base, exponent):
    return q(base, exponent)
def go():
    return run(2, 3)
q = power
print(go())
''', ALIASED),
        ('bool_base', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q(True, 3))
''', ALIASED),
        ('bool_parameter', '''
def power(base, exponent):
    return base ** exponent
q = power
def run(flag):
    return q(flag, 3)
print(run(True))
''', ALIASED),
        ('list_item', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q([2][0], [3][0]))
''', ALIASED),
        ('attribute', '''
class Box:
    base = 2
    exponent = 3
def power(base, exponent):
    return base ** exponent
q = power
print(q(Box.base, Box.exponent))
''', ALIASED),
        ('dict_value', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q({"b": 2}["b"], {"e": 3}["e"]))
''', ALIASED),
        ('float_base', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q(2.0, 3))
''', ALIASED),
        ('int_alias', '''
def convert(value):
    return int(value)
q = convert
print(q(1e300))
''', INT_FLOAT),
        ('int_alias_chain', '''
def convert(value):
    return int(value)
q = convert
r = q
print(r(1e300))
''', INT_FLOAT),
        ('int_list_item', '''
def convert(value):
    return int(value)
q = convert
print(q([1e300][0]))
''', INT_FLOAT),
        ('int_dict_value', '''
def convert(value):
    return int(value)
q = convert
print(q({"v": 1e300}["v"]))
''', INT_FLOAT),
    )

    MATCHING = (
        ('exp_safe', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q(2, 10), q(-2, 3), q(0, 1000), q(-1, 10**12))
print(q(2, 62), q(2, -1), q(10, -2))
print(q(2, 0), q(0, 0), q(-(2**63), 1), q(-2, 63))
'''),
        ('pow_safe', '''
def power(base, exponent):
    return pow(base, exponent)
BASE = 2
EXP = 10
q = power
print(q(BASE, EXP), q(2, 62))
'''),
        ('alias_chain_safe', '''
def power(base, exponent):
    return base ** exponent
q = power
r = q
print(r(2, 10))
'''),
        ('safe_base_dynamic', '''
def power(base, exponent):
    return base ** exponent
q = power
def run(n):
    return q(-1, n)
print(run(3), run(4))
'''),
        ('direct_wrapper_unchanged', '''
def power(base, exponent):
    return base ** exponent
def run(n):
    return power(2, n)
print(power(2, 10), run(3))
'''),
        ('int_safe', '''
def convert(value):
    return int(value)
q = convert
print(q(1.9), q(-1.9), q(42), q(True))
print(q(9223372036854774784.0), q(-9223372036854774784.0))
'''),
        ('int_boundary_safe', '''
def convert(value):
    return int(value)
q = convert
print(q(9223372036854775807), q(-9223372036854775808))
print(q(9007199254740992.0), q(-0.0))
'''),
        ('zero_negative_exponent', '''
def power(base, exponent):
    return base ** exponent
q = power
try:
    print(q(0, -1))
except ZeroDivisionError as error:
    print(type(error).__name__, str(error))
'''),
        ('width_boundary', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q(2, 62))
print(q(2, -62))
print(q(-2, 63))
'''),
        ('empty_zero', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q(0, 0), q(0, 5), q(5, 0), q(-1, 0))
'''),
        ('dynamic_parameter_in_range', '''
def power(base, exponent):
    return base ** exponent
q = power
def run(a, b):
    return q(a, b)
print(run(2, 3))
'''),
        ('rebound_alias', '''
def power(base, exponent):
    return base ** exponent
q = power
q = 7
print(q)
'''),
    )

    def test_unsafe_aliased_wrappers_are_refused_or_match_cpython(self):
        for general in (False, True):
            for name, source, marker in self.UNSAFE:
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pre366_' + name, source, general=general)
                    if built.returncode == 0:
                        # A path with exact big integers builds these exactly; the result
                        # must then be CPython's, never a run-time overflow.
                        expected, status = run_cpython(directory, 'pre366_' + name, source)
                        self.assertTrue(exe.exists())
                        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                        self.assertEqual(ran.returncode, status, ran.stderr)
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)
                        self.assertNotIn('integer overflow', ran.stderr)
                        continue
                    self.assertFalse(exe.exists())
                    self.assertIn(marker, built.stderr, built.stderr[-1200:])
                    self.assertNotIn('integer overflow', built.stderr)

    def test_safe_aliased_wrappers_match_cpython(self):
        for general in (False, True):
            for name, source in self.MATCHING:
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    expected, status = run_cpython(directory, 'pre366_' + name, source)
                    built, exe = compile_source(directory, 'pre366_' + name, source, general=general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual(ran.returncode, status, ran.stderr)
                    self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)


if __name__ == '__main__':
    unittest.main()
