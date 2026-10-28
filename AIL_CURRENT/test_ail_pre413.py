"""pre413: a constant integer power reached through a name is refused by name.

The pre367 review recorded as pre-existing that a constant power which only reaches `**`
through a name (a function argument, a list item, a class/instance attribute or a dict
value) compiled on both builds and then stopped with `integer overflow`, where CPython
prints the exact unbounded integer.  The compile-time binpow check now resolves the
operands through module constants, function locals, a parameter unconditionally rebound to
a constant, literal containers, class/instance attributes and constant call arguments; an
exact result outside int64 is refused with `int64 constant expression out of range`.

A value that exists only at run time keeps the documented run-time `integer overflow`
stop.  In-range powers, the int64 boundary `(-2) ** 63`, negative/float/bool operands,
dynamic values, shadowed locals and containers, and a closure that shadows a module
constant still match CPython.  Programs are built with the general path forced and with
the default build; stdout and the exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSALS = ('int64 constant out of range',
            'int64 constant expression out of range',
            'does not fit in a 64-bit signed integer',
            'outside the signed 64-bit range',
            'not in the subset')


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


class Pre413(unittest.TestCase):
    REFUSED = {
        'argument': 'def f(x):\n    return x ** 40\nprint(f(10))\n',
        'keyword_argument': 'def f(x):\n    return x ** 40\nprint(f(x=10))\n',
        'local': 'def f():\n    x = 10\n    print(x ** 40)\nf()\n',
        'local_alias': 'def f():\n    x = 10\n    y = x\n    print(y ** 40)\nf()\n',
        'local_exponent': 'def f():\n    x = 10\n    n = 40\n    print(x ** n)\nf()\n',
        'list_item': 'xs = [10]\nprint(xs[0] ** 40)\n',
        'dict_value': 'd = {"k": 10}\nprint(d["k"] ** 40)\n',
        'class_attribute': 'class Box:\n    v = 10\nprint(Box.v ** 40)\n',
        'instance_attribute': ('class Box:\n    def __init__(self, v):\n        self.v = v\n'
                               'b = Box(10)\nprint(b.v ** 40)\n'),
        'method': ('class Box:\n    def m(self):\n        x = 10\n        print(x ** 40)\n'
                   'Box().m()\n'),
        'parameter_rebound': 'def f(x):\n    x = 10\n    print(x ** 40)\nf(1)\n',
        'base_boundary': 'x = 2\nprint(x ** 63)\n',
        'argument_list_item': 'def f(v):\n    return v ** 40\nxs = [10]\nprint(f(xs[0]))\n',
        'argument_dict_value': 'def f(v):\n    return v ** 40\nd = {"k": 10}\nprint(f(d["k"]))\n',
        'argument_attribute': ('class Box:\n    v = 10\ndef f(v):\n    return v ** 40\n'
                               'print(f(Box.v))\n'),
        'negative_base': 'x = -10\nprint(x ** 41)\n',
        'tuple_nested': 'def f(x):\n    return (x ** 40,)\nprint(f(10))\n',
        'fdiv_nested': 'def f(x):\n    return x ** 40 // 1\nprint(f(10))\n',
        'closure_out_of_range': ('x = 2\ndef outer():\n    x = 10\n    def inner():\n'
                                 '        return x ** 62\n    return inner()\nprint(outer())\n'),
    }

    MATCH = {
        'in_range_argument': 'def f(x):\n    return x ** 40\nfor v in (0, 1, -1):\n    print(f(v))\n',
        'in_range_routes': ('x = 2\nxs = [2]\nd = {"k": 2}\nclass Box:\n    v = 2\n'
                            'b = Box()\nprint(x ** 62, xs[0] ** 62, d["k"] ** 62, '
                            'Box.v ** 62, b.v ** 62)\n'),
        'boundaries': ('print(2 ** 62)\nprint((-2) ** 63)\nprint((-2) ** 62)\n'
                       'print((-1) ** 41, 0 ** 40, 1 ** 40)\nprint(10 ** 18, (-10) ** 18)\n'
                       'print((2 ** 63 - 1) // 1)\nprint(10 ** 40 - 10 ** 40)\n'
                       'print(2 ** 63 - 2 ** 63)\n'),
        'types': ('x = 10\nprint(x ** -1)\nprint(x ** -40)\nprint(x ** 40.0)\n'
                  'f = 10.0\nprint(f ** 40)\nprint(True ** 40)\nprint(False ** 40)\n'),
        'dynamic': 'def f(x):\n    return x ** 2\nprint(f(10), f(-5))\n',
        'shadow_local': 'x = 10\ndef f():\n    x = 2\n    return x ** 62\nprint(f())\n',
        'shadow_container': ('xs = [10]\ndef f():\n    xs = [2]\n    return xs[0] ** 62\n'
                             'print(f())\n'),
        'parameter_rebound_in_range': 'def f(x):\n    x = 2\n    return x ** 62\nprint(f(10))\n',
        'in_range_local_exponent': ('def f():\n    x = 10\n    n = 18\n    return x ** n\n'
                                    'print(f())\n'),
        'empty_containers': 'xs = []\nd = {}\nt = ()\nprint(len(xs), len(d), len(t), xs == [])\n',
        'dynamic_argument': 'def f(x, n):\n    return x ** n\nprint(f(2, 3), f(10, 2))\n',
        'closure_shadow': ('x = 10\ndef outer():\n    x = 2\n    def inner():\n'
                           '        return x ** 62\n    return inner()\nprint(outer())\n'),
        'closure_parameter': ('p = 10\ndef outer(p):\n    def inner():\n'
                              '        return p ** 62\n    return inner()\nprint(outer(2))\n'),
        'method_closure': ('x = 10\nclass C:\n    def m(self):\n        x = 2\n'
                           '        def inner():\n            return x ** 62\n'
                           '        return inner()\nprint(C().m())\n'),
        'no_power': 'print(1 + 2)\n',
        'float_base': 'x = 10.0\nprint(x ** 40)\n',
        'pow_call_in_range': 'def f(x):\n    return pow(x, 2)\nprint(f(10))\n',
    }

    def test_out_of_range_powers_are_refused_by_name(self):
        for general in (False, True):
            for name, source in self.REFUSED.items():
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pre413_' + name, source, general=general)
                    message = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, message)
                    self.assertFalse(exe.exists())
                    self.assertTrue(any(item in message for item in REFUSALS), message)
                    self.assertNotIn('integer overflow', message)

    def test_in_range_powers_match_cpython(self):
        for name, source in self.MATCH.items():
            with tempfile.TemporaryDirectory() as directory:
                expected, status = run_cpython(directory, 'pre413_' + name, source)
            for general in (False, True):
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pre413_' + name, source, general=general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual(ran.returncode, status, ran.stderr)
                    self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)


if __name__ == '__main__':
    unittest.main()
