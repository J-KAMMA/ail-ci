"""Heterogeneous tuples through unannotated signatures reach the typed path (TUPLE_REACH.md).

A tuple passed to a parameter the source does not annotate used to keep the whole program on the general
path, even when every call site supplies the same tuple shape.  The tuple pass now collects the call-site
types, spells the agreed tuple type on the parameter and repeats until the return types settle, so a
function such as `def g(t): return t[1], t[2]` is built on the typed path.  A parameter that receives two
different shapes (or a tuple and a scalar) is left unannotated, so the program stays on the general path and
still matches CPython.  Every program is compared with CPython 3.12 byte for byte.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None


def compile_program(directory, text, name, general=False):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK', 'AIL_STRICT'):
        env.pop(key, None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                          '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True,
                         text=True, timeout=900, env=env)
    return res, exe


def run_cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=300,
                          encoding='utf-8')


def run_exe(exe):
    return subprocess.run([str(exe)], cwd=exe.parent, capture_output=True, text=True, timeout=300,
                          encoding='utf-8')


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Reach(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='tuplereach_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def compare(self, name, text, general=False):
        res, exe = compile_program(self.tmp, text, name, general)
        self.assertEqual(res.returncode, 0, name + ': ' + (res.stdout + res.stderr)[-1500:])
        want = run_cpython(self.tmp, text, name)
        got = run_exe(exe)
        self.assertEqual(got.stdout, want.stdout, name)
        self.assertEqual(got.returncode, want.returncode, name)
        return res

    def assert_typed(self, name, text):
        res = self.compare(name, text)
        self.assertNotIn('built on the general path', res.stderr,
                         name + ' fell back: ' + res.stderr[-800:])

    def assert_general(self, name, text):
        res = self.compare(name, text)
        self.assertIn('built on the general path', res.stderr,
                      name + ' was expected to stay on the general path: ' + res.stderr[-800:])
        self.compare(name + '_forced', text, general=True)


RETURN_FROM_PARAM = '''def f(n):
    return n, str(n), n / 2

def main():
    print(f(3))

main()
'''

ARGUMENT = '''def g(t):
    return t[1], t[2]

def main():
    print(g((1, "q", 2.0)))

main()
'''

LIST_ITEM = '''def g(t):
    return t[1], t[2]

def main():
    xs = [(1, "q", 2.0), (3, "r", 4.5)]
    print(g(xs[0]), g(xs[1]))

main()
'''

DICT_VALUE = '''def g(t):
    return t[1], t[2]

def main():
    d = {"k": (1, "w", 4.5)}
    print(g(d["k"]))

main()
'''

WRAPPER = '''def inner(t):
    return t[0], t[1], t[2]

def outer(t):
    return inner(t)

def main():
    print(outer((1, "a", 1.5)))

main()
'''

KEYWORD = '''def g(t):
    return t[0], t[1]

def main():
    print(g(t=(1, "a")))
    print(g(t=(2, "b")))

main()
'''

NESTED = '''def g(t):
    return t[0][1], t[1], t[0]

def main():
    print(g(((1, "a"), 2.5)))
    print(g(((3, "b"), 4.5)))

main()
'''

WIDTH_NEGATIVE = '''def g(t):
    return t[0], t[1], t[2]

def main():
    print(g((-9223372036854775808, "x", -0.0)))
    print(g((9223372036854775807, "y", 1e16)))

main()
'''

ALIAS = '''def g(t):
    return t[1], t[2]

def main():
    x = (1, "a", 2.5)
    y = x
    print(g(y))

main()
'''

BOOL_PARAM = '''def f(n):
    return n, "x"

def main():
    print(f(True))
    print(f(False))

main()
'''

LIST_PARAM = '''def g(xs):
    s = 0
    for a, b in xs:
        s += a + len(b)
    return s

def main():
    print(g([(1, "a"), (2, "bb")]))
    print(g([(3, "c")]))

main()
'''

DICT_PARAM = '''def g(d):
    return d["k"][0], d["k"][1]

def main():
    print(g({"k": (1, "a")}))
    print(g({"k": (2, "b")}))

main()
'''

SCALAR_ROUTE = '''def f(n):
    return n, str(n), n / 2

def main():
    xs = [3]
    print(f(xs[0]))
    print(f(len("ab")))

main()
'''

ATTRIBUTE_ANNOTATED = '''class C:
    def __init__(self, t: tuple[int, str, float]):
        self.t = t

def g(t):
    return t[1], t[2]

def main():
    c = C((1, "a", 1.5))
    print(g(c.t))

main()
'''

ROUTES_ANNOTATED = '''class C:
    def __init__(self, t: tuple[int, str, float]):
        self.t = t

def g(t):
    return t[0], t[1], t[2]

def main():
    xs = [(1, "a", 1.5)]
    d = {"k": (2, "b", 2.5)}
    c = C((3, "c", 3.5))
    print(g((4, "d", 4.5)))
    print(g(xs[0]))
    print(g(d["k"]))
    print(g(c.t))

main()
'''

SHAPES_CONFLICT = '''def g(t):
    return t[0], len(t)

def main():
    print(g((1, "a")))
    print(g((2, "b", 2.5)))

main()
'''

TUPLE_AND_SCALAR = '''def g(t):
    return t

def main():
    print(g((1, "a")))
    print(g(3))

main()
'''

SCALAR_CONFLICT = '''def f(n):
    return n, str(n), n / 2

def main():
    print(f(3))
    print(f(2.5))

main()
'''


class TypedReach(Reach):
    def test_return_from_parameter(self):
        self.assert_typed('tr_return', RETURN_FROM_PARAM)

    def test_argument(self):
        self.assert_typed('tr_arg', ARGUMENT)

    def test_list_item(self):
        self.assert_typed('tr_list', LIST_ITEM)

    def test_dict_value(self):
        self.assert_typed('tr_dict', DICT_VALUE)

    def test_wrapper_propagation(self):
        self.assert_typed('tr_wrap', WRAPPER)

    def test_keyword_argument(self):
        self.assert_typed('tr_kw', KEYWORD)

    def test_nested_tuple(self):
        self.assert_typed('tr_nested', NESTED)

    def test_int64_widths_and_negative_values(self):
        self.assert_typed('tr_width', WIDTH_NEGATIVE)

    def test_alias(self):
        self.assert_typed('tr_alias', ALIAS)

    def test_bool_element(self):
        self.assert_typed('tr_bool', BOOL_PARAM)

    def test_list_parameter(self):
        self.assert_typed('tr_listp', LIST_PARAM)

    def test_dict_parameter(self):
        self.assert_typed('tr_dictp', DICT_PARAM)

    def test_scalar_route(self):
        self.assert_typed('tr_scalar', SCALAR_ROUTE)

    def test_annotated_attribute(self):
        self.assert_typed('tr_attr', ATTRIBUTE_ANNOTATED)

    def test_all_routes(self):
        self.assert_typed('tr_routes', ROUTES_ANNOTATED)


class Conservative(Reach):
    def test_different_shapes_stay_general(self):
        self.assert_general('tr_shapes', SHAPES_CONFLICT)

    def test_tuple_and_scalar_stay_general(self):
        self.assert_general('tr_mixed', TUPLE_AND_SCALAR)

    def test_scalar_types_stay_general(self):
        self.assert_general('tr_scalars', SCALAR_CONFLICT)


if __name__ == '__main__':
    unittest.main()
