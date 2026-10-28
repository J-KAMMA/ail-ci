"""pre430: an aliased power wrapper is followed by the constant checks.

The rbrbpre366 review recorded the aliased-wrapper probes as pre-existing: ``q = power``
with a power wrapper body still compiled and then stopped with ``integer overflow`` where
CPython keeps the exact unbounded result, and the alias check (once present) refuses safe
bool bases and routed operands by name, which the task allows.  The checks now follow a
module-level ``q = power`` alias (and alias chains) for a wrapper whose body is exactly
``base ** exponent`` or ``pow(base, exponent)``.  Constant operands outside int64 are
refused by name; an aliased wrapper whose operands are not statically known is refused by
name too.  Safe constants and direct wrapper calls keep matching CPython.

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


class Pre430(unittest.TestCase):
    REFUSED = (
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
        ('bool_base', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q(True, 3))
''', ALIASED),
        ('bool_pow_base', '''
def power(base, exponent):
    return pow(base, exponent)
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
        ('dynamic_argument', '''
def power(base, exponent):
    return base ** exponent
def run(base, exponent):
    return q(base, exponent)
def go():
    return run(2, 3)
q = power
print(go())
''', ALIASED),
        ('list_item', '''
def power(base, exponent):
    return base ** exponent
q = power
print(q([2][0], [3][0]))
''', ALIASED),
        ('class_attribute', '''
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
        ('direct_wrapper_unchanged', '''
def power(base, exponent):
    return base ** exponent
def run(n):
    return power(2, n)
print(power(2, 10), run(3))
'''),
        ('dynamic_parameter_in_range', '''
def power(base, exponent):
    return base ** exponent
q = power
def run(a, b):
    return q(a, b)
print(run(2, 3))
'''),
    )

    def test_aliased_power_wrappers_are_refused_by_name(self):
        for general in (False, True):
            for name, source, marker in self.REFUSED:
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pre430_' + name, source, general=general)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertFalse(exe.exists())
                    self.assertIn(marker, built.stderr, built.stderr[-1200:])
                    self.assertNotIn('integer overflow', built.stderr)

    def test_safe_aliased_power_wrappers_match_cpython(self):
        for general in (False, True):
            for name, source in self.MATCHING:
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    expected, status = run_cpython(directory, 'pre430_' + name, source)
                    built, exe = compile_source(directory, 'pre430_' + name, source, general=general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual(ran.returncode, status, ran.stderr)
                    self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)


if __name__ == '__main__':
    unittest.main()
