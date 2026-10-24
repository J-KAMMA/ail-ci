"""pre56: a known integer power whose exact result leaves int64 is refused at compile time.

CPython keeps an unbounded int for `10 ** 40` and `pow(10, 40)`; this compiler has only
64-bit integers (SEMANTICS section 1), and the runtime used to stop with `integer overflow`.
When the operands are compile-time constants -- directly, through a module or local name, a
list item, a dict value or a class attribute -- the compiler now refuses the construct by name
on both builds instead of emitting a program that can only trap.

Powers whose exact result still fits are unchanged, including `(-2) ** 63` (INT64_MIN),
`2 ** 62`, a modular `pow()`, negative exponents (the float path) and a shadowed `pow`.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
MESSAGE = 'the integer'

OVERFLOW = {
    'module_name': 'a = 10\nprint(a**40)\n',
    'builtin_pow': 'print(pow(10, 40))\n',
    'local_name': 'def f():\n    a = 10\n    return a**40\nprint(f())\n',
    'nested_constant': 'A = 10\ndef outer():\n    def inner():\n        return A**40\n'
                       '    return inner()\nprint(outer())\n',
    'list_item': 'xs = [10]\nprint(xs[0]**40)\n',
    'dict_value': 'd = {0: 10}\nprint(d[0]**40)\n',
    'class_attribute': 'class C:\n    a = 10\nprint(C.a**40)\n',
    'negative_base': 'print((-10)**41)\n',
    'power_boundary': 'print(3**40)\n',
    'pow_boundary': 'print(pow(2, 63))\n',
}

VALID = r'''class Box:
    def __init__(self, v):
        self.v = v


class C:
    a = 2


def helper(x):
    return x**40


def shadowed():
    a = 10
    return [a**80 for a in [1]]


def same(a, b):
    return a**b


def user_pow(a, b):
    return a + b


def main():
    xs = [2]
    d = {0: 2}
    box = Box(2)
    print(2**62, (-2)**63, 3**39, 10**18)
    print(pow(2, 62), pow(2, 63, 1000), pow(2, -1), 2**-1)
    print(0**100, 1**100, (-1)**101, 0**0)
    print(xs[0]**40, d[0]**40, C.a**40, box.v**40)
    print(helper(2), same(2, 40))
    print(shadowed())
    print([x**2 for x in [2, 3]], [x**80 for x in [1]])
    print(user_pow(10, 40))


main()
'''


SAFE = {
    'list_mutated': 'xs = [10]\nxs[0] = 1\nprint(xs[0]**40)\n',
    'dict_mutated': 'd = {0: 10}\nd[0] = 1\nprint(d[0]**40)\n',
    'list_aliased_mutated': 'xs = [10]\nys = xs\nys[0] = 1\nprint(xs[0]**40)\n',
    'dict_aliased_mutated': 'd = {0: 10}\ne = d\ne[0] = 1\nprint(d[0]**40)\n',
    'list_mutated_by_argument': 'xs = [10]\ndef f(y):\n    y[0] = 1\nf(xs)\nprint(xs[0]**40)\n',
    'param_shadows_class': 'class C:\n    a = 10\ndef f(C):\n    return C.a**40\nprint(1)\n',
    'enclosing_shadows_module': 'A = 10\ndef outer(A):\n    def inner():\n'
                                '        return A**40\n    return inner()\nprint(outer(2))\n',
    'nested_container_mutated': 'xs = [[10]]\nys = xs[0]\nys[0] = 1\n'
                                'print(xs[0][0]**40)\n',
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', src.name], cwd=directory, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def build(directory, name, text, *, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    done = subprocess.run([sys.executable, '-B', str(CLI), 'compile', src.name, '--syntax', 'python',
                           '-o', exe.name], cwd=directory, capture_output=True, text=True,
                          timeout=900, env=env)
    return done, exe


class Pre56Tests(unittest.TestCase):
    def test_overflowing_constant_power_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre56-') as directory:
            for case, text in OVERFLOW.items():
                for general in (True, False):
                    with self.subTest(case=case, general=general):
                        done, _ = build(directory, '%s_%s' % (case, 'g' if general else 'd'),
                                        text, general=general)
                        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
                        self.assertIn(MESSAGE, done.stderr)
                        self.assertIn('64-bit signed integer', done.stderr)
                        self.assertNotIn('Traceback', done.stderr)

    def test_mutated_or_shadowed_constants_are_not_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre56-safe-') as directory:
            for case, text in SAFE.items():
                want, rc, err = cpython(directory, case, text)
                self.assertEqual(rc, 0, err.decode('utf-8', 'replace'))
                for general in (True, False):
                    with self.subTest(case=case, general=general):
                        done, exe = build(directory, '%s_%s' % (case, 'g' if general else 'd'),
                                          text, general=general)
                        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                        got = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                             timeout=120)
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want,
                                         got.stderr.decode('utf-8', 'replace'))
                        self.assertEqual(got.returncode, 0)

    def test_valid_powers_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre56-') as directory:
            want, rc, err = cpython(directory, 'main', VALID)
            self.assertEqual(rc, 0, err.decode('utf-8', 'replace'))
            for general in (True, False):
                with self.subTest(general=general):
                    done, exe = build(directory, 'main_%s' % ('g' if general else 'd'),
                                      VALID, general=general)
                    self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                    got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want,
                                     got.stderr.decode('utf-8', 'replace'))
                    self.assertEqual(got.returncode, 0)


if __name__ == '__main__':
    unittest.main()
