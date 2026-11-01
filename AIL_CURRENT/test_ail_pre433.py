"""Pre433: a power base bound from a function default matches CPython under exact ints.

The rbpre386 review recorded ``def f(x=10): print(x**40); f()`` as a pre-existing difference:
both builds compiled it and then stopped with ``integer overflow`` where CPython prints the
bignum.  The constant-power pass followed a parameter to explicit call-site arguments but not
to the parameter's default, so a call that omitted it stayed unknown.  The default is now
evaluated in the defining scope and used when a call omits the parameter; in the int64 era that
made the power refuse by name at compile time (``int64 constant expression out of range``).

Integers are int64 by default (ail-ci#198), so a Python-syntax default build refuses the
out-of-range power by name at compile time; ``--exact-int`` / ``AIL_EXACT_INT=1`` prints the
same integer CPython does and never overflows.  Covered on both builds: a positional, leading
or keyword-only default; a negative default; a default read from a module alias, a list item, a
class attribute or a dict value; the width boundaries around 10**18 and 2**63; an explicit
argument at the same call; and a constant ``*`` argument.  In-range defaults, a call that passes
an in-range value, bases 0/1/-1, bool and float defaults, and a function that is never called
also match CPython.

The test probes the compiler's integer mode with ``10 ** 40``.  In the int64 default the
out-of-range cases must keep the named refusal; the explicit exact-mode tests build them and
compare with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general, exact=False):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d') + ('e' if exact else 'i'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if exact:
        env['AIL_EXACT_INT'] = '1'
    else:
        env.pop('AIL_EXACT_INT', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True,
                               timeout=900, env=env)


REFUSED = {
    'default': '''
def f(x=10):
    print(x**40)

f()
''',
    'negative_default': '''
def f(x=-10):
    print(x**40)

f()
''',
    'mixed_call_sites': '''
def f(x=10):
    print(x**40)

f(2)
f()
''',
    'named_default': '''
def f(x=10):
    print(x**40)

f(x=10)
''',
    'leading_default': '''
def f(a, x=10):
    print(a, x**40)

f(1)
''',
    'kwonly_default': '''
def f(*, x=10):
    print(x**40)

f()
''',
    'empty_star_default': '''
def f(x=10):
    print(x**40)

f(*())
''',
    'expanded_star_argument': '''
def f(x=10):
    print(x**40)

f(*(10,))
''',
    'module_alias': '''
M = 10
N = M

def f(x=N):
    print(x**40)

f()
''',
    'list_item': '''
def f(x=[10][0]):
    print(x**40)

f()
''',
    'attribute': '''
class Box:
    v = 10

def f(x=Box.v):
    print(x**40)

f()
''',
    'dict_value': '''
def f(x={"k": 10}["k"]):
    print(x**40)

f()
''',
    'decimal_boundary': '''
def f(x=10):
    print(x**19)

f()
''',
    'binary_boundary': '''
def f(x=2):
    print(x**63)

f()
''',
    'explicit_out_of_range': '''
def f(x):
    print(x**40)

f(10)
''',
}

MATCH = {
    'explicit_safe': '''
def f(x=10):
    print(x**40)

f(2)
''',
    'named_safe': '''
def f(x=10):
    print(x**40)

f(x=2)
''',
    'kwonly_safe': '''
def f(*, x=10):
    print(x**40)

f(x=2)
''',
    'no_call': '''
def f(x=10):
    print(x**40)

print("unused")
''',
    'decimal_boundary_safe': '''
def f(x=10):
    print(x**18)

f()
''',
    'binary_boundary_safe': '''
def f(x=2):
    print(x**62)

f()
''',
    'safe_bases': '''
def a(x=0):
    print(x**40)

def b(x=1):
    print(x**40)

def c(x=-1):
    print(x**40)

a()
b()
c()
''',
    'bool_float_defaults': '''
def f(x=True):
    print(x**40)

def g(y=2.0):
    print(y**40)

f()
g()
''',
    'safe_alias_default': '''
M = 2
N = M

def f(x=N):
    print(x**40)

f()
''',
    'star_safe': '''
def f(x=10):
    print(x**40)

f(*(2,))
''',
    'empty_star_safe': '''
def f(x=2):
    print(x**40)

f(*())
''',
}


class Pre433(unittest.TestCase):
    def exact_integer_mode(self, directory, general):
        """Whether this build keeps exact integers, probed with a power beyond int64."""
        name = 'integer_mode_' + ('g' if general else 'd')
        text = 'print(10 ** 40)\n'
        want = cpython(directory, name, text)
        exe, built = build(directory, name, text, general)
        message = built.stdout + built.stderr
        self.assertNotIn('Traceback', message)
        if built.returncode != 0:
            self.assertTrue(any(text in message for text in (
                'int64 constant expression out of range', 'int64 constant out of range',
                'does not fit in a 64-bit signed integer')), message)
            return False
        got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], message)
        self.assertEqual(got.returncode, want[1], message)
        return True

    def test_default_power_out_of_int64_matches_or_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre433-') as directory:
            for general in (True, False):
                exact = self.exact_integer_mode(directory, general)
                for name, text in REFUSED.items():
                    with self.subTest(case=name, general=general, exact=exact):
                        want = cpython(directory, name, text)
                        exe, built = build(directory, name + ('g' if general else 'd'), text, general)
                        message = built.stdout + built.stderr
                        if not exact:
                            self.assertNotEqual(built.returncode, 0, message)
                            self.assertIn('int64 constant expression out of range', message)
                            self.assertNotIn('Traceback', message)
                            self.assertNotIn('integer overflow', message)
                            continue
                        self.assertEqual(built.returncode, 0, message)
                        got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                         (name, general, got.stderr[-800:]))
                        self.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))

    def test_default_power_with_exact_ints_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre433-exact-') as directory:
            for name, text in REFUSED.items():
                want = cpython(directory, name, text)
                for general in (True, False):
                    with self.subTest(case=name, general=general):
                        exe, built = build(directory, name + ('g' if general else 'd'), text,
                                           general, exact=True)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                             cwd=directory)
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                         (name, general, got.stderr[-800:]))
                        self.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))

    def test_in_range_and_explicit_routes_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre433-') as directory:
            for name, text in MATCH.items():
                want = cpython(directory, name, text)
                for general in (True, False):
                    with self.subTest(case=name, general=general):
                        exe, built = build(directory, name + ('g' if general else 'd'), text, general)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                         (name, general, got.stderr[-800:]))
                        self.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))

    def test_int64_check_mode_still_refuses_the_default(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre433-check-') as directory:
            for general in (True, False):
                src = Path(directory) / ('check_' + ('g' if general else 'd') + '.py')
                src.write_text(REFUSED['default'], encoding='utf-8')
                env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
                env.pop('AIL_NO_GENERAL', None)
                env.pop('AIL_EXACT_INT', None)
                if general:
                    env['AIL_UNIFIED_FORCE'] = '1'
                else:
                    env.pop('AIL_UNIFIED_FORCE', None)
                checked = subprocess.run([sys.executable, '-B', CHATGPT, 'check', src.name,
                                          '--syntax', 'python'], cwd=directory, capture_output=True,
                                         text=True, timeout=900, env=env)
                self.assertIn('int64 constant expression out of range',
                              checked.stdout + checked.stderr)


if __name__ == '__main__':
    unittest.main()
