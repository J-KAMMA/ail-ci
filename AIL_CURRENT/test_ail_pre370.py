"""Pre370: int() of a statically known item of a function parameter is refused when it is out of int64.

A reviewer of pre358 left ``def show(xs): print(int(xs[0])); show([1e300])`` open: both builds
compiled it and then stopped with ``integer overflow`` where CPython prints the big integer.  The
int64 call check now follows a constant subscript of a function parameter to the call sites, so
the conversion is refused by name (``int() of a float outside int64`` for a float, ``int64
constant expression out of range`` for text or bytes).  Covered: a list, tuple, dict key, nested
item, negative index and keyword-only parameter; a single local alias of the parameter; an index
held in a module constant; the argument reaching the call as a list item, a dict value, a class
attribute or a module container alias; a wrapper function; and two call sites where one is out of
range.  In-range values, int64 boundaries, an empty list, a callee that overwrites the item and a
dynamic argument keep the run-time route and match CPython.
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
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_refused(test, name, text, needle):
    with tempfile.TemporaryDirectory(prefix='ail-pre370-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(needle, message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre370-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


FLOAT_REFUSED = {
    'arg_list_float': '''
def show(xs):
    print(int(xs[0]))

show([1e300])
''',
    'tuple_arg': '''
def show(xs):
    print(int(xs[0]))

show((1e300,))
''',
    'negative_index': '''
def show(xs):
    print(int(xs[-1]))

show([1e300])
''',
    'nested_item': '''
def show(xs):
    print(int(xs[0][1]))

show([[0, 1e300]])
''',
    'wrapper': '''
def show(xs):
    print(int(xs[0]))

def wrap(ys):
    show(ys)

wrap([1e300])
''',
    'argument_from_list_item': '''
vals = [1e300]

def show(xs):
    print(int(xs[0]))

show([vals[0]])
''',
    'argument_from_attribute': '''
class Box:
    v = 1e300

def show(xs):
    print(int(xs[0]))

show([Box.v])
''',
    'module_alias': '''
vals = [1e300]
alias = vals

def show(xs):
    print(int(xs[0]))

show(alias)
''',
    'local_alias': '''
def show(xs):
    ys = xs
    print(int(ys[0]))

show([1e300])
''',
    'index_from_constant': '''
IDX = 0

def show(xs):
    print(int(xs[IDX]))

show([1e300])
''',
    'keyword_only': '''
def show(*, xs):
    print(int(xs[0]))

show(xs=[1e300])
''',
    'mixed_call_sites': '''
def show(xs):
    print(int(xs[0]))

show([1.5])
show([1e300])
''',
    'float_boundary': '''
def show(xs):
    print(int(xs[0]))

show([9223372036854775808.0])
''',
}

INT_REFUSED = {
    'arg_list_text': '''
def show(xs):
    print(int(xs[0]))

show(["9223372036854775808"])
''',
    'arg_list_bytes': '''
def show(xs):
    print(int(xs[0]))

show([b"-9223372036854775809"])
''',
    'dict_key': '''
def show(xs):
    print(int(xs["k"]))

show({"k": "9223372036854775808"})
''',
    'argument_from_dict_value': '''
d = {"k": "9223372036854775808"}

def show(xs):
    print(int(xs[0]))

show([d["k"]])
''',
}

MATCH = {
    'float_in_range': '''
def show(xs):
    print(int(xs[0]))

show([1.5])
show([-2.75])
''',
    'text_int_in_range': '''
def show(xs):
    print(int(xs[0]))

show(["42"])
show(["-7"])
''',
    'int_boundaries': '''
def show(xs):
    print(int(xs[0]))

show([9223372036854775807])
show([-9223372036854775808])
''',
    'float_boundary_in_range': '''
def show(xs):
    print(int(xs[0]))

show([-9223372036854775808.0])
show([9.223372036854774e18])
''',
    'bool_items': '''
def show(xs):
    print(int(xs[0]))

show([True])
show([False])
''',
    'local_alias_in_range': '''
def show(xs):
    ys = xs
    print(int(ys[0]))

show([1.5])
''',
    'constant_index_in_range': '''
IDX = 0

def show(xs):
    print(int(xs[IDX]))

show(["42"])
''',
    'empty_list': '''
def show(xs):
    try:
        print(int(xs[0]))
    except IndexError as error:
        print("IndexError", str(error))

show([])
''',
    'mutated_by_callee': '''
def show(xs):
    xs[0] = 1.0
    print(int(xs[0]))

show([1e300])
''',
    'dynamic_argument': '''
import sys

def show(xs):
    print(int(xs[0]))

value = float(sys.argv[1]) if len(sys.argv) > 1 else 1.5
show([value])
''',
    'no_int_use': '''
def show(xs):
    print(xs[0])

show([1e300])
''',
}


class Pre370Tests(unittest.TestCase):
    def test_parameter_item_outside_int64_is_refused(self):
        for slug, text in FLOAT_REFUSED.items():
            with self.subTest(case=slug):
                check_refused(self, slug, text, 'int() of a float outside int64')
        for slug, text in INT_REFUSED.items():
            with self.subTest(case=slug):
                check_refused(self, slug, text, 'int64 constant expression out of range')

    def test_in_range_empty_mutated_and_dynamic_routes_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
