"""pre298: repr(e.args[i]) keeps the argument's own kind on the typed path.

e.args[i] reads as text, so repr(e.args[i]) used to repr that text: a numeric argument
printed as '3.0' where CPython prints 3.0.  The typed path now has a repr accessor that
formats the stored argument, so ints, floats, bools, None and strs keep CPython's repr.
"""
import unittest

from test_ail_pathlib import Base

PROGRAM = r'''
def show(i: int) -> None:
    try:
        raise ValueError("it's", -2.5, 7, True, None, "日本")
    except ValueError as e:
        if i == 0:
            print(repr(e.args[0]))
        elif i == 1:
            print(repr(e.args[1]))
        elif i == 2:
            print(repr(e.args[2]))
        elif i == 3:
            print(repr(e.args[3]))
        elif i == 4:
            print(repr(e.args[4]))
        elif i == 5:
            print(repr(e.args[5]))
        elif i == 6:
            print(repr(e.args[-2]))
        elif i == 7:
            print(f"{e.args[1]!r} {e.args[2]!r}")
        elif i == 8:
            print("%r %r" % (e.args[1], e.args[2]))
        else:
            try:
                print(repr(e.args[6]))
            except IndexError as x:
                print(type(x).__name__, x)


def main() -> None:
    for i in range(10):
        show(i)


main()
'''

SINGLE = r'''
def main() -> None:
    try:
        raise ValueError(7)
    except ValueError as e:
        print(repr(e.args[0]), "%r" % e.args[0], f"{e.args[0]!r}")
    try:
        raise ValueError(-7)
    except ValueError as e:
        print(repr(e.args[0]), "%r" % e.args[0], f"{e.args[0]!r}")
    try:
        raise ValueError(True)
    except ValueError as e:
        print(repr(e.args[0]), "%r" % e.args[0], f"{e.args[0]!r}")
    try:
        raise ValueError(None)
    except ValueError as e:
        print(repr(e.args[0]), "%r" % e.args[0], f"{e.args[0]!r}")
    try:
        raise ValueError(-0.0)
    except ValueError as e:
        print(repr(e.args[0]), "%r" % e.args[0], f"{e.args[0]!r}")
    try:
        raise ValueError(1e300)
    except ValueError as e:
        print(repr(e.args[0]), "%r" % e.args[0], f"{e.args[0]!r}")
    try:
        raise ValueError("a'b")
    except ValueError as e:
        print(repr(e.args[0]), "%r" % e.args[0], f"{e.args[0]!r}")
    try:
        raise ValueError("日本")
    except ValueError as e:
        print(repr(e.args[0]), len(e.args), str(e.args[0]))


main()
'''

ROUTES = r'''
def index_of(x: int) -> int:
    return x


def main() -> None:
    box = [4]
    d = {"i": 3}
    for k in (-1, -2, 0, 1):
        try:
            raise ValueError("s", 2, 3.5, False, None)
        except ValueError as e:
            try:
                print(k, repr(e.args[k]))
            except IndexError as x:
                print(k, type(x).__name__, x)
        try:
            raise ValueError("s", 2, 3.5, False, None)
        except ValueError as e:
            print("call", repr(e.args[index_of(k)]))
        try:
            raise ValueError("s", 2, 3.5, False, None)
        except ValueError as e:
            print("list", repr(e.args[box[0]]))
        try:
            raise ValueError("s", 2, 3.5, False, None)
        except ValueError as e:
            print("dict", repr(e.args[d["i"]]))
    try:
        raise ValueError("a", -2.5, 7, True, None, "日")
    except ValueError as e:
        print(f"{e.args[1]!r:>16}")
        print(f"{e.args[2]!r:.>8}")
        print("%r=%r" % (e.args[2], e.args[3]))
        print("%r %s %r" % (e.args[0], e.args[1], e.args[2]))
        print(str(e.args), e.args)
        print(repr(e.args[1]) + "|" + repr(e.args[0]))


main()
'''


class Pre298Tests(Base):
    def test_repr_of_numeric_exception_arguments(self):
        self.compare("args_repr_numeric", PROGRAM, mode="typed")

    def test_repr_of_single_exception_argument(self):
        self.compare("args_repr_single", SINGLE, mode="typed")

    def test_repr_routes_and_formats(self):
        self.compare("args_repr_routes", ROUTES, mode="typed")


if __name__ == "__main__":
    unittest.main()
