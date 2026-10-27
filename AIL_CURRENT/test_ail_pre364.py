"""A wide constant ``pow`` exponent with a run-time base is refused by name.

The rbpre331 record left one gap open: when the integer base of ``pow(base, (3**100)>>150)``
reaches the call through a parameter, list item, class/instance attribute or dict value, the
constant folder could not see it, so both builds compiled the program and then stopped with
``integer overflow`` where CPython prints the bignum.  The checker now refuses the symmetric
shape -- a constant exponent of at least 63 (2**63 already leaves int64) with a base computed
at run time -- and binds a plain function's module-level constant arguments, so the exact
result is folded when the base and exponent both arrive as parameters.  Safe bases (0/1/-1,
bool and float), exponents below 63, negative exponents and a program that binds its own
``pow`` keep matching CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = (
    ('argument', 'def power(b):\n    print(pow(b, (3**100)>>150))\n\n\npower(2)\n'),
    ('list_item', 'values = [2]\nprint(pow(values[0], (3**100)>>150))\n'),
    ('class_attribute', 'class Box:\n    base = 2\n\n\nprint(pow(Box.base, (3**100)>>150))\n'),
    ('instance_attribute', 'class Box:\n    pass\n\n\nbox = Box()\nbox.base = 2\n'
                           'print(pow(box.base, (3**100)>>150))\n'),
    ('dict_value', 'print(pow({"b": 2}["b"], (3**100)>>150))\n'),
    ('parameter_exponent', 'def power(b):\n    print(pow(b, 63))\n\n\npower(2)\n'),
    ('both_parameters', 'def power(b, e):\n    print(pow(b, e))\n\n\n'
                         'power(2, (3**100)>>150)\n'),
    ('repeated_call', 'def power(b):\n    print(pow(b, 63))\n\n\npower(2)\npower(2)\n'),
    ('alias_inside', 'def power(b):\n    p = pow\n    print(p(b, 63))\n\n\npower(2)\n'),
    ('never_called', 'def power(b):\n    print(pow(b, (3**100)>>150))\n'),
)

SAFE = r'''def power(base, exponent):
    return pow(base, exponent)


def scaled_float(b):
    return pow(b, (3**100)>>150)


def scaled_bool(b):
    return pow(b, (3**100)>>150)


def main():
    print(pow(0, (3**100)>>150), pow(1, (3**100)>>150), pow(-1, (3**100)>>150))
    print(pow(True, (3**100)>>150), pow(2.0, (3**100)>>150))
    print(pow(2, 62), pow(-2, 63), pow(3, 39))
    print(pow(2, -((3**100)>>150)))
    print(pow(2, (3**100)>>150, 1000))
    print([pow(0, (3**100)>>150), pow(1, (3**100)>>150)][1])
    print(power(2.0, (3**100)>>150))
    print(power(True, (3**100)>>150))
    print(power(1, (3**100)>>150))
    print(power(2, 10))
    print(power(3, 39))
    p = pow
    print(p(2, 10))
    base = 2
    exponent = 10
    print(pow(base, exponent))


main()
print(scaled_float(2.0))
print(scaled_bool(True))
'''

SHADOWED = r'''def pow(base, exponent):
    return 7


def power(b):
    return pow(b, 63)


def main():
    print(power(2))


main()
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


class Pre364(unittest.TestCase):
    def test_a_wide_constant_exponent_refuses_a_runtime_base_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre364-') as directory:
            for name, text in REFUSED:
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        status, _, output = build_run(directory, text, name, general)
                        self.assertNotEqual(status, 0, output)
                        self.assertTrue('int64 constant expression out of range' in output
                                        or 'base computed at run time' in output, output)
                        self.assertNotIn('integer overflow', output)
                        self.assertNotIn('Traceback', output)

    def test_safe_bases_and_exponents_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre364-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', SAFE], capture_output=True, timeout=120)
            self.assertEqual(want.returncode, 0, want.stderr)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, SAFE, 'safe', general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)

    def test_a_program_that_binds_its_own_pow_is_left_alone(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre364-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', SHADOWED], capture_output=True, timeout=120)
            self.assertEqual(want.returncode, 0, want.stderr)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, SHADOWED, 'shadowed', general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)


if __name__ == '__main__':
    unittest.main()
