"""pre310: the rbrbpre47 review's first pre-existing difference, `2 ** 63`.

CPython has unbounded ints and prints 9223372036854775808; an AIL int is int64
(SEMANTICS section 1), so the value has no representation here.  This tree already
refuses the construct by name at compile time on both builds (the generic constant
checks from pre121/pre177/pre97), so no compiler change is needed.  The test locks
that named refusal for the whole list the review recorded, plus the routes a value
can take and the in-range int64 boundaries, which must still match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


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
                           text=True, timeout=600, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


REFUSALS = ('int64 constant out of range',
            'int64 constant expression out of range',
            'does not fit in a 64-bit signed integer',
            'outside the signed 64-bit range',
            'not in the subset')


class Pre310(unittest.TestCase):
    CASES = (
        ('pow', 'print(2 ** 63)\n'),
        ('shift', 'print(1 << 63)\n'),
        ('decimal', 'print(10 ** 40)\n'),
        ('pow10000', 'print(2 ** 10000)\n'),
        ('pow_huge', 'print(2 ** 100000000)\n'),
        ('negated_power', 'print(-(-2) ** 63)\n'),
        ('fstring', 'print(f"{2 ** 63}")\n'),
        ('float_sum', 'print(2 ** 63 + 0.5)\n'),
        ('split_maxsplit', 'print("a".split(",", 2 ** 63))\n'),
        ('negated_min', 'print(-2 ** 63 - 1)\n'),
    )

    ROUTES = (
        ('assigned', 'value = 2 ** 63\nprint(value)\n'),
        ('argument', 'def show(x):\n    print(x)\n\nshow(2 ** 63)\n'),
        ('list', 'print([2 ** 63][0])\n'),
        ('dict', 'print({0: 2 ** 63}[0])\n'),
        ('attribute', 'class Box:\n    value = 2 ** 63\n\nprint(Box.value)\n'),
        ('alias', 'a = 2 ** 63\nb = a\nprint(b)\n'),
        ('module_constant', 'VALUE = 2 ** 63\nprint(VALUE)\n'),
        ('returned', 'def show():\n    return 2 ** 63\n\nprint(show())\n'),
    )

    def test_out_of_range_constants_are_refused_by_name(self):
        for general in (False, True):
            for name, source in self.CASES:
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pre310_' + name, source, general=general)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertFalse(exe.exists())
                    self.assertTrue(any(message in built.stderr for message in REFUSALS), built.stderr)

    def test_first_case_through_routes_is_refused_by_name(self):
        for general in (False, True):
            for name, source in self.ROUTES:
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pre310_route_' + name, source, general=general)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertFalse(exe.exists())
                    self.assertTrue(any(message in built.stderr for message in REFUSALS), built.stderr)

    def test_in_range_boundaries_still_match_cpython(self):
        source = '''def show(x):
    print(x)


print(2 ** 63 - 1)
print(-(2 ** 63))
print(1 << 62)
print(2 ** 63 - 2 ** 63)
print((2 ** 70) // (2 ** 10))
print((2 ** 63) >> 1)
print(f"{2 ** 63 - 1}")
show((2 ** 63 - 1) // 3)
show([(-2) ** 63][0])
print(0 ** 200, 1 ** 200, (-1) ** 201)
'''
        with tempfile.TemporaryDirectory() as directory:
            expected, status = run_cpython(directory, 'pre310_in_range', source)
        for general in (False, True):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_source(directory, 'pre310_in_range', source, general=general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                self.assertEqual(ran.returncode, status, ran.stderr)
                self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)


if __name__ == '__main__':
    unittest.main()
