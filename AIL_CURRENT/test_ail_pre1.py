"""Pre-existing difference from CPython: positional-only parameters (`def f(x, /)`).

The modules3 review recorded that `kwonly_default` with positional-only parameters was a named
refusal on both builds. The general path now binds positional-only parameters in order, gives them
their defaults, and still refuses by name a call that passes one as a keyword. These programs are
compared with CPython 3.12 on the legacy and IR paths.
"""
import subprocess
import sys
import unittest

from test_ail_modules import CLI, ModulesBase, write


class PositionalOnly(ModulesBase):
    def test_defaults_and_values_through_calls(self):
        files = {
            'main.py': '''BASE = 10


def pick(a, /, b=BASE, *, c=-1, d=BASE + 1):
    return (a, b, c, d)


def text(a, /, b="x"):
    return a + b


def over(a: int, /, b: int = 3) -> int:
    return a * b


def main():
    print(pick(1))
    print(pick(-5, 0, c=-1, d=0))
    print(pick("q", b="r", c="s"))
    print(text("a"), text("a", ""), text("", "z"))
    print(over(4), over(4, 5))
    values = [7, 8, 9]
    print(pick(values[0]), pick(values[-1], values[1]))
    print(pick(1.5, 2.5), pick(True, False), pick(None, None))
    print(pick((1, 2), (3,)), pick({"a": 1}, b={"b": 2}))
    print(pick([], b=[1]), pick(0, 0))


main()
''',
        }
        self.assertEqual(self.same_as_cpython(files),
                         "(1, 10, -1, 11)\n"
                         "(-5, 0, -1, 0)\n"
                         "('q', 'r', 's', 11)\n"
                         "ax a z\n"
                         "12 20\n"
                         "(7, 10, -1, 11) (9, 8, -1, 11)\n"
                         "(1.5, 2.5, -1, 11) (True, False, -1, 11) (None, None, -1, 11)\n"
                         "((1, 2), (3,), -1, 11) ({'a': 1}, {'b': 2}, -1, 11)\n"
                         "([], [1], -1, 11) (0, 0, -1, 11)\n")

    def test_methods_static_methods_and_nested_defs(self):
        files = {
            'main.py': '''class C:
    def __init__(self, x, /):
        self.x = x

    def add(self, y, /, z=1):
        return self.x + y + z

    @staticmethod
    def s(a, /, b=2):
        return a * b


def outer(a, /, b=10):
    def inner(c, /, d=1):
        return a + b + c + d

    print(inner(3, d=4))
    print(inner(5))
    print(inner(-1, 0))


def main():
    c = C(5)
    print(c.x, c.add(2), c.add(2, 3), c.add(2, z=4))
    print(C.s(3), C.s(3, 4))
    print(C(-2).add(-3, z=-4))
    outer(1, b=2)
    outer(10)


main()
''',
        }
        self.assertEqual(self.same_as_cpython(files),
                         "5 8 10 11\n"
                         "6 12\n"
                         "-9\n"
                         "10\n"
                         "9\n"
                         "2\n"
                         "27\n"
                         "26\n"
                         "19\n")

    def test_varargs_and_aliasing(self):
        files = {
            'main.py': '''def f(a, /, *rest, **kw):
    return (a, rest, sorted(kw.items()))


def g(a, /, b=2, *rest):
    return (a, b, rest)


def mutate(a, /, b):
    a.append(10)
    b.append(20)
    return a is b, len(a), len(b)


def main():
    print(f(1))
    print(f(1, 2, 3))
    print(f(1, 2, x=3, y=4))
    print(g(1))
    print(g(1, 2))
    print(g(1, 2, 3, 4))
    print(g(*[9]))
    print(g(*[9, 8, 7]))
    xs = []
    print(mutate(xs, xs), xs)
    table = {"k": []}
    print(mutate(table["k"], table["k"]), table)


main()
''',
        }
        self.assertEqual(self.same_as_cpython(files),
                         "(1, (), [])\n"
                         "(1, (2, 3), [])\n"
                         "(1, (2,), [('x', 3), ('y', 4)])\n"
                         "(1, 2, ())\n"
                         "(1, 2, ())\n"
                         "(1, 2, (3, 4))\n"
                         "(9, 2, ())\n"
                         "(9, 8, (7,))\n"
                         "(True, 2, 2) [10, 20]\n"
                         "(True, 2, 2) {'k': [10, 20]}\n")

    def test_a_positional_only_name_as_a_keyword_is_refused(self):
        write(self.dir, {'main.py': '''def f(a, /, b=2):
    return a + b


print(f(1, a=3))
'''})
        out = self.dir / 'out'
        built = subprocess.run([sys.executable, '-B', CLI, 'compile', 'main.py', '-o', str(out)],
                               cwd=self.dir, capture_output=True, text=True, timeout=120)
        self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn('not in the subset', built.stderr)
        self.assertIn('positional-only argument a as a keyword', built.stderr)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
