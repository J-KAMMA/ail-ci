"""pre386: a `**` power whose base arrives through a route is refused by name when it leaves int64.

The pre364 review left the ``**``-routed case unverified.  Reproduced on both builds:
``def f(x): print(x ** 40)`` / ``f(10)`` compiled and then stopped with ``integer
overflow``, where CPython prints the exact 41-digit integer; the same happened with the base
through a keyword argument, an alias, an identity wrapper, a tuple item, a function-local
constant, a list item, a dict value, ``dict.get`` and a class/instance attribute.  The
compile-time checker now resolves the base through those routes and refuses the exact power
by name instead of emitting the int64 trap.  On this tree the pre367 pass already resolves
the same routes, so the refusal is the existing generic ``int64 constant expression out of
range``; both that wording and pre386's ``does not fit in a 64-bit signed integer`` are
accepted.  A base that is not statically known, the safe bases -1/0/1, negative exponents,
float and bool bases, in-range powers and the pre273 constant-base rule are unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')

REFUSALS = ('does not fit in a 64-bit signed integer',
            'int64 constant expression out of range')

REFUSED = (
    ('argument', 'def f(x):\n    print(x ** 40)\n\nf(10)\n'),
    ('argument_keyword', 'def f(x):\n    print(x ** 40)\n\nf(x=10)\n'),
    ('argument_alias', 'def f(x):\n    print(x ** 40)\n\ny = 10\nf(y)\n'),
    ('argument_identity', 'def idf(v):\n    return v\n\n'
                          'def f(x):\n    print(x ** 40)\n\nf(idf(10))\n'),
    ('argument_tuple', 'def f(x):\n    print(x ** 40)\n\nt = (10, 5)\nf(t[0])\n'),
    ('argument_boundary', 'def f(x):\n    print(x ** 63)\n\nf(2)\n'),
    ('argument_assigned', 'def f(x):\n    y = x ** 40\n    print(y)\n\nf(10)\n'),
    ('argument_negative', 'def f(x):\n    print(x ** 41)\n\nf(-10)\n'),
    ('local_constant', 'def f():\n    x = 10\n    print(x ** 40)\n\nf()\n'),
    ('list_item', 'xs = [10]\nprint(xs[0] ** 40)\n'),
    ('dict_value', "d = {'v': 10}\nprint(d['v'] ** 40)\n"),
    ('local_list_item', 'def f():\n    xs = [10]\n    print(xs[0] ** 40)\n\nf()\n'),
    ('local_dict_value', "def f():\n    d = {'v': 10}\n    print(d['v'] ** 40)\n\nf()\n"),
    ('dict_get', "d = {'v': 10}\nprint(d.get('v') ** 40)\n"),
    ('class_attribute', 'class C:\n    v = 10\n\nprint(C.v ** 40)\n'),
    ('instance_attribute', 'class C:\n    v = 10\n\nprint(C().v ** 40)\n'),
)

MATCHING = (
    ('argument_in_range', 'def f(x):\n    print(x ** 3)\n\nf(10)\n'),
    ('argument_in_range_large', 'def f(x):\n    print(x ** 62)\n\nf(2)\n'),
    ('list_in_range', 'xs = [2]\nprint(xs[0] ** 62)\n'),
    ('dict_in_range', "d = {'b': 3}\nprint(d['b'] ** 39)\n"),
    ('local_list_in_range', 'def f():\n    xs = [2]\n    print(xs[0] ** 62)\n\nf()\n'),
    ('local_dict_in_range', "def f():\n    d = {'b': 3}\n    print(d['b'] ** 39)\n\nf()\n"),
    ('attribute_in_range', 'class C:\n    v = 3\n\nprint(C().v ** 39)\n'),
    ('safe_bases', 'for b in (0, 1, -1):\n    print(b ** 1000000)\n'
                   'xs = [1]\nprint(xs[0] ** 63)\n'),
    ('negative_exponent', 'xs = [10]\nprint(xs[0] ** -1)\n'),
    ('float_and_bool', 'xs = [2.0]\nprint(xs[0] ** 40)\n'
                       'bs = [True]\nprint(bs[0] ** 40)\nprint(True ** 63)\n'),
    ('zero_and_one', 'xs = [10]\nprint(xs[0] ** 0)\nprint(xs[0] ** 1)\n'),
    ('in_range_boundary', 'print(2 ** 62)\nprint(2 ** 63 - 1)\nprint(-(2 ** 63))\n'),
    ('no_power', 'xs = [1, 2, 3]\nprint(sum(xs), min(xs), max(xs))\n'
                 "print({'a': 1}.get('a'))\n"),
)


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          cwd=directory, env=dict(os.environ, PYTHONUTF8='1',
                                                  PYTHONWARNINGS='ignore'))


class Pre386(unittest.TestCase):
    def test_routed_power_exact_matches_cpython(self):
        for general in (False, True):
            for name, text in REFUSED:
                with self.subTest(name=name, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre386-') as directory:
                    want = cpython(directory, name, text)
                    exe, built = build(directory, name, text, general)
                    self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                         cwd=directory)
                    self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_routed_power_in_range_matches_cpython(self):
        for general in (False, True):
            for name, text in MATCHING:
                with self.subTest(name=name, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre386-') as directory:
                    want = cpython(directory, name, text)
                    exe, built = build(directory, name, text, general)
                    self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                         cwd=directory)
                    self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_constant_base_runtime_exponent_matches_cpython(self):
        text = 'es = [40]\nprint(10 ** es[0])\n'
        for general in (False, True):
            with self.subTest(general=general), \
                    tempfile.TemporaryDirectory(prefix='ail-pre386-') as directory:
                want = cpython(directory, 'constant_base', text)
                exe, built = build(directory, 'constant_base', text, general)
                self.assertEqual(built.returncode, 0, (general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (general, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()
