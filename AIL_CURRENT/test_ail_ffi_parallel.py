"""A parallel body never calls a foreign C function (`@extern` stub), directly or through a wrapper fn."""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'python' / 'pkg-v12'))
import parallel  # noqa: E402


class Refused(Exception):
    pass


SOURCE = '''
@extern(lib="z", header="zlib.h", symbol="foo")
def foo(x: int) -> int: ...

def wrap(x: int) -> int:
    return foo(x) + 1
'''


def _funcs():
    tree = ast.parse(SOURCE)
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _check(name):
    funcs = _funcs()
    parallel.check_callee(funcs[name], funcs, Refused, ())


class ExternInParallelBody(unittest.TestCase):
    def test_extern_refused_by_name(self):
        with self.assertRaises(Refused) as cm:
            _check('foo')
        self.assertIn('extern foo() is a C function', str(cm.exception))

    def test_extern_through_wrapper_refused(self):
        with self.assertRaises(Refused) as cm:
            _check('wrap')
        self.assertIn('extern foo() is a C function', str(cm.exception))

    def test_plain_fn_unchanged(self):
        funcs = {n.name: n for n in ast.parse('def f(x: int) -> int:\n    return x * 2\n').body}
        parallel.check_callee(funcs['f'], funcs, Refused, ())


if __name__ == '__main__':
    unittest.main()
