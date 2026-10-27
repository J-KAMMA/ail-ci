"""pre332: out-of-int64 integer powers through names, arguments and containers.

The pre321 review recorded that an out-of-int64 integer power compiled and then stopped
with ``integer overflow`` where CPython prints the exact unbounded integer, when the base
and exponent reached the power through a variable, an argument, a list item, an attribute
or a dict value.  The front end now resolves those operands when they are statically known
(module/local constants, safe containers, class/instance attributes and simple wrapper
calls) and refuses the construct by name on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSALS = ('int64 constant expression out of range',
            'int64 constant out of range')


def compile_source(directory, name, source, general=False):
    path = Path(directory) / (name + '.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            path.name, '--syntax', 'python', '-o', exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=600, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory,
                         capture_output=True, text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre332(unittest.TestCase):
    REFUSED = (
        ('literal', 'print(10 ** 19)\n'),
        ('variable', 'x = 10\nprint(x ** 19)\n'),
        ('both_variables', 'x = 10\ne = 19\nprint(x ** e)\n'),
        ('argument', 'def power(b, e):\n    return b ** e\n\nprint(power(10, 19))\n'),
        ('local', 'def f():\n    x = 10\n    return x ** 19\n\nprint(f())\n'),
        ('list_item', 'xs = [10]\nprint(xs[0] ** 19)\n'),
        ('local_list', 'def f():\n    xs = [10]\n    return xs[0] ** 19\n\nprint(f())\n'),
        ('dict_value', 'd = {"b": 10}\nprint(d["b"] ** 19)\n'),
        ('class_attribute', 'class Box:\n    b = 10\n\nprint(Box.b ** 19)\n'),
        ('instance_attribute',
         'class Box:\n    def __init__(self):\n        self.b = 10\n\nprint(Box().b ** 19)\n'),
        ('pow_argument',
         'def power(b, e):\n    return pow(b, e)\n\nprint(power(10, 19))\n'),
        ('pow_list_item', 'xs = [10]\nprint(pow(xs[0], 19))\n'),
        ('pow_alias', 'p = pow\nprint(p(10, 19))\n'),
        ('cancellation_names', 'x = 10\ny = 10\nprint((x ** 19) - (y ** 19))\n'),
    )

    MATCHING = '''def power(b, e):
    return b ** e


xs = [10]
d = {"b": 10}


class Box:
    b = 10


class Inst:
    def __init__(self):
        self.b = 10


print(power(10, 18))
print(power(xs[0], 18))
print(power(d["b"], 18))
print(power(Box.b, 18))
print(power(Inst().b, 18))
print(power(2, 62), power(-2, 63), power(3, 39))
print(2 ** 62, (-2) ** 63, 3 ** 39)
print(power(0, 10 ** 12), power(1, 10 ** 12))
print(power(-1, 10 ** 12), power(-1, 10 ** 12 + 1))
print(power(True, 19), power(False, 19))
print(power(2, 0), power(2, 1))
print(2 ** -1)
ys = [10]
ys[0] = 2
print(ys[0] ** 19)
nested = [[10]]
nested[0][0] = 2
print(nested[0][0] ** 19)
nested_tuple = ([10],)
nested_tuple[0][0] = 2
print(nested_tuple[0][0] ** 19)
nested_dict = {"k": [10]}
nested_dict["k"][0] = 2
print(nested_dict["k"][0] ** 19)


def nested_local():
    xs = [[10]]
    xs[0][0] = 2
    return xs[0][0] ** 19


def nested_local_tuple():
    t = ([10],)
    t[0][0] = 2
    return t[0][0] ** 19


print(nested_local())
print(nested_local_tuple())


class NestedClass:
    xs = [[10]]


NestedClass.xs[0][0] = 2
print(NestedClass.xs[0][0] ** 19)


def unused():
    x = 10
    return x ** 19


def unused_nested():
    xs = [[10]]
    xs[0][0] = 2
    return xs[0][0] ** 19


class UnusedMethod:
    def m(self):
        x = 10
        return x ** 19


def outer():
    def inner():
        x = 10
        return x ** 19

    return 5


print(outer())
print("ok")
'''

    def test_out_of_range_powers_are_refused_by_name(self):
        for general in (False, True):
            for name, source in self.REFUSED:
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pre332_' + name, source, general=general)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertFalse(exe.exists())
                    self.assertTrue(any(message in built.stderr for message in REFUSALS),
                                    built.stderr)

    def test_in_range_and_mutated_values_still_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            expected, status = run_cpython(directory, 'pre332_matching', self.MATCHING)
        for general in (False, True):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_source(directory, 'pre332_matching', self.MATCHING,
                                            general=general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                self.assertEqual(ran.returncode, status, ran.stderr)
                self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)


if __name__ == '__main__':
    unittest.main()
