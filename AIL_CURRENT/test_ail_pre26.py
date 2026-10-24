"""pre26: repr(e.args[i]) keeps the argument's own kind on the typed path.

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


class Pre26Tests(Base):
    def test_repr_of_numeric_exception_arguments(self):
        self.compare("args_repr_numeric", PROGRAM, mode="typed")


if __name__ == "__main__":
    unittest.main()
