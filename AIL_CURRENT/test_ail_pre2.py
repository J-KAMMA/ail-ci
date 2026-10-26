"""A constant integer power whose exact value leaves int64 is refused at compile time.

`2 ** 63` is 9223372036854775808 in CPython, which has unbounded ints; an AIL int is int64
(SEMANTICS section 1), so the operation has no answer here. The value is known while compiling,
so the compiler names the construct and stops instead of leaving a run-time `integer overflow`.
In-range constant powers, including the negative INT64_MIN spelling `(-2) ** 63`, are unchanged.

Re-applied on the current tree: the generic constant-expression rule already refuses the
out-of-range power (and the assignment forms) by name, so this test accepts its wording as well
as the original power-specific wording.  The newer exact-fold rule keeps `2 ** 63 - 1` in range,
so that expression is checked against CPython instead of being refused.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_source(directory, name, source, syntax='python', general=False):
    path = Path(directory, name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory, name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', syntax, '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=600, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory, name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


REFUSALS = ('int64 constant power out of range',
            'int64 constant out of range',
            'int64 constant expression out of range',
            'outside the signed 64-bit range')


class ConstantPowerOverflow(unittest.TestCase):
    CASES = (
        ('direct', 'print(2 ** 63)\n'),
        ('assigned', 'value = 2 ** 63\nprint(value)\n'),
        ('negative_base', 'print((-2) ** 64)\n'),
        ('huge_exponent', 'print(2 ** 100000000)\n'),
    )

    def test_out_of_range_constant_powers_are_refused_by_name(self):
        for general in (False, True):
            for name, source in self.CASES:
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pow_' + name, source, general=general)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertFalse(exe.exists())
                    self.assertTrue(any(message in built.stderr for message in REFUSALS), built.stderr)

    def test_ail_syntax_refuses_the_same_construct(self):
        source = 'fn main() { print(2 ** 63); }\n'
        for general in (False, True):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_source(directory, 'pow_ail', source, syntax='ail', general=general)
                self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertFalse(exe.exists())
                self.assertTrue(any(message in built.stderr for message in REFUSALS), built.stderr)

    def test_in_range_constant_powers_still_match_cpython(self):
        source = '''def main():
    print(2 ** 62)
    print((-2) ** 63)
    print(2 ** 63 - 1)
    print((2 ** 63) >> 1)
    print(2 ** 63 - 2 ** 63)
    print(0 ** 200, 1 ** 200, (-1) ** 201)
    print(2 ** -1)
    print(2.0 ** 63)


main()
'''
        with tempfile.TemporaryDirectory() as directory:
            expected, status = run_cpython(directory, 'in_range', source)
        for general in (False, True):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_source(directory, 'in_range', source, general=general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                self.assertEqual(ran.returncode, status, ran.stderr)
                self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)


if __name__ == '__main__':
    unittest.main()
