"""pre367: a constant integer power that only reaches `**` through a name matches CPython.

CPython's int is unbounded, so `x = 10; print(x ** 40)` prints the exact 41-digit value.  For the
int64 era the power was refused by name at compile time; under exact ints it builds on both builds
and prints the exact integer.  The cases resolve the value behind the power inside a function body
(its own int locals and a parameter it unconditionally rebinds to a constant), through a literal
list, tuple or dict read by subscript, through a class or instance attribute, and through a
constant argument to a function that raises it to a constant exponent.  A nested function's free
name resolves to the value the enclosing function scope binds, not to a same-named module
constant, so a closure that shadows a module constant is neither wrongly folded nor wrongly
computed.  In-range powers, boundaries and run-time-only values match CPython as well.
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
                           text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre367(unittest.TestCase):
    EXACT = {
        'argument': 'def f(x):\n    return x ** 40\nprint(f(10))\n',
        'keyword_argument': 'def f(x):\n    return x ** 40\nprint(f(x=10))\n',
        'local': 'def f():\n    x = 10\n    print(x ** 40)\nf()\n',
        'local_alias': 'def f():\n    x = 10\n    y = x\n    print(y ** 40)\nf()\n',
        'local_exponent': 'def f():\n    x = 10\n    n = 40\n    print(x ** n)\nf()\n',
        'list_item': 'xs = [10]\nprint(xs[0] ** 40)\n',
        'list_alias': 'xs = [10]\nys = xs\nprint(ys[0] ** 40)\n',
        'class_attribute': 'class Box:\n    v = 10\nprint(Box.v ** 40)\n',
        'instance_attribute': ('class Box:\n    def __init__(self, v):\n        self.v = v\n'
                               'b = Box(10)\nprint(b.v ** 40)\n'),
        'dict_value': 'd = {"k": 10}\nprint(d["k"] ** 40)\n',
        'tuple_nested': 'def f(x):\n    return (x ** 40,)\nprint(f(10))\n',
        'fdiv_nested': 'def f(x):\n    return x ** 40 // 1\nprint(f(10))\n',
        'negative_base': 'x = -10\nprint(x ** 41)\n',
        'method': 'class Box:\n    def m(self):\n        x = 10\n        print(x ** 40)\nBox().m()\n',
        'parameter_rebound': 'def f(x):\n    x = 10\n    print(x ** 40)\nf(1)\n',
        'base_boundary': 'x = 2\nprint(x ** 63)\n',
        'alias_int': 'x = 10\ny = x\nprint(y ** 40)\n',
        'argument_list_item': 'def f(v):\n    return v ** 40\nxs = [10]\nprint(f(xs[0]))\n',
        'argument_dict_value': 'def f(v):\n    return v ** 40\nd = {"k": 10}\nprint(f(d["k"]))\n',
        'closure_out_of_range': ('x = 2\ndef outer():\n    x = 10\n    def inner():\n'
                                 '        return x ** 62\n    return inner()\nprint(outer())\n'),
        'closure_negative_out_of_range': ('x = 2\ndef outer():\n    x = -10\n    def inner():\n'
                                          '        return x ** 41\n    return inner()\nprint(outer())\n'),
        'closure_out_of_range_exponent': ('x = 2\ndef outer():\n    n = 63\n    def inner():\n'
                                          '        return x ** n\n    return inner()\nprint(outer())\n'),
    }

    MATCH = {
        'in_range_argument': 'def f(x):\n    return x ** 40\nfor v in (0, 1, -1):\n    print(f(v))\n',
        'in_range_routes': ('x = 2\nxs = [2]\nys = xs\nd = {"k": 2}\nclass Box:\n    v = 2\n'
                            'b = Box()\nprint(x ** 62, xs[0] ** 62, ys[0] ** 62, d["k"] ** 62, '
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
        'in_range_local_exponent': 'def f():\n    x = 10\n    n = 18\n    return x ** n\nprint(f())\n',
        'empty_containers': 'xs = []\nd = {}\nt = ()\nprint(len(xs), len(d), len(t), xs == [])\n',
        'dynamic_argument': 'def f(x, n):\n    return x ** n\nprint(f(2, 3), f(10, 2))\n',
        'closure_shadow': ('x = 10\ndef outer():\n    x = 2\n    def inner():\n'
                           '        return x ** 62\n    return inner()\nprint(outer())\n'),
        'closure_parameter': ('p = 10\ndef outer(p):\n    def inner():\n'
                              '        return p ** 62\n    return inner()\nprint(outer(2))\n'),
        'method_closure': ('x = 10\nclass C:\n    def m(self):\n        x = 2\n'
                           '        def inner():\n            return x ** 62\n'
                           '        return inner()\nprint(C().m())\n'),
        'closure_deep': ('x = 10\ndef grand():\n    x = 2\n    def middle():\n'
                         '        def inner():\n            return x ** 62\n'
                         '        return inner()\n    return middle()\nprint(grand())\n'),
        'closure_global_decl': ('x = 2\ndef outer():\n    global x\n    def inner():\n'
                                '        return x ** 62\n    return inner()\nprint(outer())\n'),
        'closure_container': ('xs = [10]\ndef outer():\n    xs = [2]\n    def inner():\n'
                              '        return xs[0] ** 62\n    return inner()\nprint(outer())\n'),
        'closure_instance': ('class Box:\n    def __init__(self, v):\n        self.v = v\n'
                             'b = Box(10)\ndef outer():\n    b = Box(2)\n    def inner():\n'
                             '        return b.v ** 62\n    return inner()\nprint(outer())\n'),
        'closure_rebound': ('x = 10\ndef outer():\n    x = 3\n    x = 2\n    def inner():\n'
                            '        return x ** 62\n    return inner()\nprint(outer())\n'),
        'closure_default_arg': ('x = 10\ndef outer():\n    x = 2\n    def inner(v=x):\n'
                                '        return v ** 62\n    return inner()\nprint(outer())\n'),
        'closure_exponent': ('x = 2\ndef outer():\n    n = 62\n    def inner():\n'
                             '        return x ** n\n    return inner()\nprint(outer())\n'),
        'closure_def_name_shadow': ('helper = 10\ndef outer():\n    def helper():\n'
                                    '        return 2\n    def inner():\n'
                                    '        return helper ** 62\n    return inner()\n'
                                    'print(outer())\n'),
    }

    def check_cases(self, cases):
        for name, source in cases.items():
            with tempfile.TemporaryDirectory() as directory:
                expected, status = run_cpython(directory, 'pre367_' + name, source)
            for general in (False, True):
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pre367_' + name, source, general=general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual(ran.returncode, status, ran.stderr)
                    self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)

    def test_out_of_range_powers_match_cpython(self):
        self.check_cases(self.EXACT)

    def test_in_range_powers_match_cpython(self):
        self.check_cases(self.MATCH)


if __name__ == '__main__':
    unittest.main()
