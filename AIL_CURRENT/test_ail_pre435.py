"""pre435: int() of a default argument captured before a container mutation is refused.

The pre393 review recorded as pre-existing that ``M = [1e300];
def f(x=M[0]): return int(x); M[0] = 1; print(f())`` stopped with ``integer overflow`` on
both builds, where CPython prints the exact big integer.  The int() check read the module
constants after the whole body had run, so the later item store had already dropped ``M``;
the default is evaluated once, when the definition runs, so it still holds 1e300.

Each top-level definition now has its parameter defaults evaluated with the names visible at
that statement, and the call-site int() wrapper check uses those values when a call omits the
argument.  Direct conversions written in a default are checked at the definition too.  The
same value is covered through a list, tuple, dict, alias, negative index, keyword-only
parameter, a container default, an attribute, a module constant and a wrapper call, for a
float, string and bytes, at and beyond the int64 boundaries.  In-range values, a mutation
before the definition, an explicit argument overriding the default and an unused function
still match CPython.
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


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
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


def check_refused(test, name, text, needle):
    with tempfile.TemporaryDirectory(prefix='ail-pre435-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(needle, message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre435-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                             (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


FLOAT = 'int() of a float outside int64'
INT = 'int64 constant expression out of range'

REFUSED = {
    'list_mutation_after': ('''
M = [1e300]
def f(x=M[0]): return int(x)
M[0] = 1
print(f())
''', FLOAT),
    'dict_mutation_after': ('''
D = {"k": 1e300}
def f(x=D["k"]): return int(x)
D["k"] = 1
print(f())
''', FLOAT),
    'list_no_mutation': ('''
M = [1e300]
def f(x=M[0]): return int(x)
print(f())
''', FLOAT),
    'dict_no_mutation': ('''
D = {"k": 1e300}
def f(x=D["k"]): return int(x)
print(f())
''', FLOAT),
    'literal_float': ('''
def f(x=1e300): return int(x)
print(f())
''', FLOAT),
    'tuple_item': ('''
T = (1e300,)
def f(x=T[0]): return int(x)
print(f())
''', FLOAT),
    'attribute': ('''
class Box:
    v = 1e300
def f(x=Box.v): return int(x)
print(f())
''', FLOAT),
    'list_item': ('''
VALS = [0, 1e300]
def f(x=VALS[1]): return int(x)
print(f())
''', FLOAT),
    'dict_value': ('''
VALS = {"k": 1e300}
def f(x=VALS["k"]): return int(x)
print(f())
''', FLOAT),
    'alias': ('''
M = [1e300]
N = M
def f(x=N[0]): return int(x)
M[0] = 1
print(f())
''', FLOAT),
    'negative_index': ('''
M = [1.5, 1e300]
def f(x=M[-1]): return int(x)
M[-1] = 2
print(f())
''', FLOAT),
    'keyword_only': ('''
def f(*, x=1e300): return int(x)
print(f())
''', FLOAT),
    'container_list_default': ('''
def f(xs=[1e300]): return int(xs[0])
print(f())
''', FLOAT),
    'container_dict_default': ('''
def f(d={"k": 1e300}): return int(d["k"])
print(f())
''', FLOAT),
    'module_alias': ('''
K = 1e300
L = K
def f(x=L): return int(x)
print(f())
''', FLOAT),
    'float_2_pow_63': ('''
def f(x=9223372036854775808.0): return int(x)
print(f())
''', FLOAT),
    'float_below_min': ('''
def f(x=-9223372036854777856.0): return int(x)
print(f())
''', FLOAT),
    'string_out_of_int64': ('''
def f(x="9223372036854775808"): return int(x)
print(f())
''', INT),
    'bytes_out_of_int64': ('''
def f(x=b"9223372036854775808"): return int(x)
print(f())
''', INT),
    'int_in_default': ('''
M = [1e300]
def f(x=int(M[0])): return x
M[0] = 1
print(f())
''', FLOAT),
    'multiple_calls': ('''
def f(x=1e300): return int(x)
print(f(1.5))
print(f())
''', FLOAT),
    'wrapper_call': ('''
M = [1e300]
def f(x=M[0]): return int(x)
def g(): return f()
print(g())
''', FLOAT),
    'second_parameter': ('''
def f(a, x=1e300): return int(x)
print(f(1))
''', FLOAT),
}

MATCHED = {
    'in_range_list_mutation_after': '''
M = [1.5]
def f(x=M[0]): return int(x)
M[0] = 2
print(f())
''',
    'explicit_override': '''
M = [1e300]
def f(x=M[0]): return int(x)
print(f(1.5))
''',
    'mutation_before_definition': '''
M = [1e300]
M[0] = 1
def f(x=M[0]): return int(x)
print(f())
''',
    'int_default_in_range': '''
def f(x=7): return int(x)
print(f())
''',
    'bool_default': '''
def f(x=True): return int(x)
print(f())
''',
    'negative_in_range': '''
def f(x=-1.5): return int(x)
print(f())
''',
    'min_boundary_float': '''
def f(x=-9223372036854775808.0): return int(x)
print(f())
''',
    'empty_container_default': '''
def f(xs=[]): return len(xs)
print(f())
''',
    'dynamic_default': '''
def f(x=float("1.5")): return int(x)
print(f())
''',
    'dict_in_range_mutation_after': '''
D = {"k": 1.5}
def f(x=D["k"]): return int(x)
D["k"] = 2
print(f())
''',
    'string_in_range_default': '''
def f(x="7"): return int(x)
print(f())
''',
    'function_never_called': '''
M = [1e300]
def f(x=M[0]): return int(x)
print(0)
''',
    'container_list_in_range': '''
def f(xs=[1, 2]): return int(xs[1])
print(f())
''',
    'container_dict_get': '''
def f(d={"k": 2.5}): return int(d.get("k"))
print(f())
''',
    'string_min_default': '''
def f(x="-9223372036854775808"): return int(x)
print(f())
''',
    'float_below_2_pow_63': '''
def f(x=9223372036854774784.0): return int(x)
print(f())
''',
}


class Pre435Tests(unittest.TestCase):
    def test_out_of_int64_default_capture_is_refused_by_name(self):
        for name, (text, needle) in REFUSED.items():
            with self.subTest(name=name):
                self.assertEqual(cpython(tempfile.gettempdir(), 'pre435_' + name, text)[1], 0)
                check_refused(self, name, text, needle)

    def test_in_range_default_capture_matches_cpython(self):
        for name, text in MATCHED.items():
            with self.subTest(name=name):
                check_program(self, name, text)


if __name__ == '__main__':
    unittest.main()
