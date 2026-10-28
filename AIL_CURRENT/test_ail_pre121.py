"""pre121: constant int expressions are folded; out-of-int64 constants are refused by name.

pre97's reviewer recorded that ``2**63 - 1`` in ordinary arithmetic, a user function called
with ``10**30``, and a variable holding ``2**63 - 1`` still died at run time with
``integer overflow`` where CPython keeps an unbounded int.  The compiler now evaluates an
all-constant int expression exactly as it sees it: an in-range value is emitted as one
literal (including a value reached through a wider intermediate), and a value that does not
fit is refused by name on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

IN_RANGE = r'''def show(tag, value):
    print(tag, value)


def get(value):
    return value


MAX = 2**63 - 1
POWER = 2**100 // 2**80
xs = [2**63 - 1]
d = {"v": -(2**63)}


class Box:
    n = (2**100) // (2**100) * (2**63 - 1)


def main():
    show("max", 2**63 - 1)
    show("min", -(2**63))
    show("min2", -1 << 63)
    show("min3", (-2)**63)
    show("notmin", ~(-2**63))
    show("shift", 1 << 62)
    show("negshift", -1 << 62)
    show("zero", 0**0)
    show("floordiv", 7 // -2)
    show("mod", 7 % -2)
    show("negfloordiv", -7 // 2)
    show("negmod", -7 % 2)
    show("mul", 2**10 * 2**20)
    show("shiftdiv", (1 << 40) >> 20)
    show("xor", (2**40) ^ (2**20))
    show("and", (2**40 + 3) & 255)
    show("or", (1 << 20) | 7)
    show("sub", 2**62 + 2**62 - 1)
    show("invert", ~0)
    show("power_max", (2**200) // (2**200) * (2**63 - 1))
    show("intermediate", 2**100 // 2**80)
    show("intermediate2", 2**64 >> 2)
    show("const", MAX)
    show("const2", POWER)
    show("arg", get(2**62 + 2**62 - 1))
    show("list", xs[0])
    show("dict", d["v"])
    show("attr", Box.n)


main()
'''

DYNAMIC = r'''class Box:
    def __init__(self, n):
        self.n = n


def cut(n):
    return n // -2, n % -2, n ** 2, n << 2


def main():
    n = 7
    xs = [n]
    d = {"n": n}
    b = Box(n)
    print(cut(n), cut(xs[0]), cut(d["n"]), cut(b.n))
    print(n ** 2, n << 2, n // -2, n % -2)
    print(2 ** -1, (-2) ** 3, 2.0 ** 3, 2 ** 3.0)
    print(True + 1, True * 3, True << 2, False | 3)


main()
'''

P6_USER_SPLIT = r'''def split(sep, n):
    return [sep, n]


def main():
    print(split(" ", 10**30))
    xs = [10**30]
    print(split(",", xs[0]))
    d = {"n": -10**30}
    print(split(":", d["n"]))


main()
'''

P7_PLAIN = r'''x = 2**63 - 1
print(x)
y = 2**100 // 2**80
print(y)
z = 1 << 63
print(z)
'''

P13_MAXSPLIT_VARIABLE = r'''N = 2**63 - 1
print("a b c".split(" ", N))
print("a b c".rsplit(" ", N))
M = 10**30
print("a b c".split(" ", M))
'''

OUT_OF_RANGE = [
    ('pow_arg', 'def f(n):\n    return n\n\n\nprint(f(10**30))\n'),
    ('pow_list', 'xs = [10**30]\nprint(xs)\n'),
    ('pow_dict', 'd = {"n": -10**30}\nprint(d)\n'),
    ('pow_attr', 'class Box:\n    n = 10**30\n\n\nb = Box()\nprint(b.n)\n'),
    ('pow_return', 'def f():\n    return 10**30\n\n\nprint(f())\n'),
    ('pow_module', 'N = 10**30\nprint(N)\n'),
    ('shift_over', 'print(1 << 63)\n'),
    ('pow_over', 'print(2**63)\n'),
    ('neg_pow_over', 'print((-2)**64)\n'),
    ('mod_over', 'print((2**100) % (2**80 + 1))\n'),
]

REFUSALS = ('outside the signed 64-bit range',
            'int64 constant expression out of range',
            'int64 constant out of range')


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre121Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre121-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def check_refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre121-') as directory:
            # exact ints (bigint): builds and matches CPython (stdout, exit code)
            want, want_rc, _err = _cpython(directory, slug, text)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                 % (text[:2000], general, build_err))

    def test_constant_int_expressions_in_range(self):
        self.check('in_range', IN_RANGE)

    def test_dynamic_and_non_int_expressions_unchanged(self):
        self.check('dynamic', DYNAMIC)

    def test_pre97_user_split_with_huge_int_refused(self):
        self.check_refused('p6_user_split', P6_USER_SPLIT)

    def test_pre97_plain_constants_refused(self):
        self.check_refused('p7_plain', P7_PLAIN)

    def test_pre97_maxsplit_variable_refused(self):
        self.check_refused('p13_variable', P13_MAXSPLIT_VARIABLE)

    def test_constant_above_int64_refused(self):
        for slug, text in OUT_OF_RANGE:
            self.check_refused(slug, text)


if __name__ == '__main__':
    unittest.main()
