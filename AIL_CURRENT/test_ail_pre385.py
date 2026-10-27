"""A power whose constant operands reach it through calls is refused by name (job pre385).

The pre364 review recorded two pre-existing differences: ``u1_nested_call`` (both parameters of
a function routed through another call into ``b ** e``) and ``v1_mixed_sites`` (a safe module
call plus a nested ``f(2)`` with a wide constant exponent) compiled on both builds and then
stopped with ``integer overflow`` where CPython prints the bignum.  The shared compile pass now
follows module-scope calls into plain functions, binding parameters to statically known argument
values; a ``**`` (or ``pow()``) operand that follows such a parameter and whose exact result
leaves int64 is refused by name on both builds.  Calls the fold cannot resolve, powers whose
result fits, and values that reach the power only at run time keep matching CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = (
    ('nested_call', 'def power(b, e):\n    return b ** e\n\n\n'
                    'def apply(a, b):\n    return power(a, b)\n\n\n'
                    'print(apply(2, (3**100) >> 150))\n'),
    ('mixed_sites', 'def f(x):\n    return x ** 63\n\n\n'
                    'print(f(1))\n\n\ndef g():\n    return f(2)\n\n\nprint(g())\n'),
    ('direct_module_call', 'def power(b, e):\n    return b ** e\n\n\nprint(power(2, 100))\n'),
    ('argument_wrapper', 'def power(b, e):\n    return b ** e\n\n\n'
                         'def go(x, y):\n    return power(x, y)\n\n\nprint(go(2, 100))\n'),
    ('pow_nested_call', 'def power(b, e):\n    return pow(b, e)\n\n\n'
                        'def apply(a, b):\n    return power(a, b)\n\n\n'
                        'print(apply(2, (3**100) >> 150))\n'),
    ('list_item', 'def power(b, e):\n    return b ** e\n\n\n'
                  'values = [2, 100]\nprint(power(values[0], values[1]))\n'),
    ('alias', 'def power(b, e):\n    return b ** e\n\n\n'
              'base = 2\nvalues = [base, 100]\nalias = values\n'
              'print(power(alias[0], alias[1]))\n'),
    ('class_attribute', 'def power(b, e):\n    return b ** e\n\n\n'
                        'class Box:\n    base = 2\n\n\nprint(power(Box.base, 100))\n'),
    ('dict_value', 'def power(b, e):\n    return b ** e\n\n\n'
                   'settings = {"b": 2, "e": 100}\n'
                   'print(power(settings["b"], settings["e"]))\n'),
    ('exponent_63', 'def power(b, e):\n    return b ** e\n\n\nprint(power(2, 63))\n'),
    ('huge_exponent', 'def power(b, e):\n    return b ** e\n\n\n'
                      'print(power(2, 1 << 20))\n'),
    ('store_after_power', 'def power(b, e):\n    v = b ** e\n    b = 1\n    return v\n\n\n'
                          'print(power(2, 100))\n'),
)

SAFE = r'''def power(b, e):
    return b ** e


def fixed(x):
    return x ** 63


def main():
    print(power(2, 10), power(2, 62), power(-2, 63))
    print(power(0, 100), power(1, 100), power(-1, 71), power(True, 100))
    print(power(2.0, 100), power(1.5, 10), power(2, -3))
    print(power(2, len("abc")))
    values = [2, 100]
    values[1] = 10
    print(power(values[0], values[1]))
    print(fixed(0), fixed(1), fixed(-1))
    print(pow(2, 10))


main()
'''

# A parameter the callee stores to does not carry its call argument into the power: the
# reported value is one the callee overwrites, so binding it would refuse a valid program.
REBOUND = r'''def power(b, e):
    return b ** e


def assign(b, e):
    b = 1
    return b ** e


def loop(b, e):
    for b in (1,):
        pass
    return b ** e


def augment(b, e):
    b *= 0
    return b ** e


def conditional(b, e):
    if b > 1:
        b = 1
    return b ** e


def outer(b, e):
    b = 1
    return power(b, e)


def loop_store(b, e):
    total = 0
    for x in (1, 2):
        total = total + b ** e
        b = 1
    return total


base = 2


def shadowed(base, e):
    return power(base, e)


print(assign(2, 100), loop(2, 100), augment(2, 100), conditional(2, 100))
print(outer(2, 100), shadowed(1, 100), loop_store(2, 10))
'''


def build_run(directory, text, name, general):
    src = Path(directory) / ('%s.py' % name)
    exe = Path(directory) / ('%s_%s' % (name, 'g' if general else 'd'))
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return built.returncode, b'', built.stdout + built.stderr
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return ran.returncode, ran.stdout.replace(b'\r\n', b'\n'), built.stdout + built.stderr


def run_cpython(directory, text, name):
    src = Path(directory) / ('%s_cpython.py' % name)
    src.write_text(text, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', src.name], cwd=directory,
                         capture_output=True, text=True,
                         env=dict(os.environ, PYTHONUTF8='1'), timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre385(unittest.TestCase):
    def test_routed_powers_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre385-') as directory:
            for name, text in REFUSED:
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        status, _, output = build_run(directory, text, name, general)
                        self.assertNotEqual(status, 0, output)
                        self.assertIn('int64 constant expression out of range', output)
                        self.assertIn('through a call', output)
                        self.assertNotIn('Traceback', output)
                        self.assertNotIn('integer overflow', output)

    def test_in_range_and_dynamic_powers_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre385-') as directory:
            want = run_cpython(directory, SAFE, 'safe')
            for general in (False, True):
                with self.subTest(general=general):
                    got = build_run(directory, SAFE, 'safe', general)
                    self.assertEqual((got[1].decode('utf-8'), got[0]), want, got[2])

    def test_rebound_parameters_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre385-') as directory:
            want = run_cpython(directory, REBOUND, 'rebound')
            self.assertEqual(want, ('1 1 0 1\n1 1 1025\n', 0))
            for general in (False, True):
                with self.subTest(general=general):
                    got = build_run(directory, REBOUND, 'rebound', general)
                    self.assertEqual((got[1].decode('utf-8'), got[0]), want, got[2])


if __name__ == '__main__':
    unittest.main()
