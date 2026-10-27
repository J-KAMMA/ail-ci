"""pre334: a store into e.args[i] from a nested handler reaching the outer exception.

CPython raises TypeError for `e.args[0] = ...` and prints a traceback AIL does not model.  A
nested handler is in the enclosing function's scope, so a store there that reaches the outer
handler's name is now refused by name at compile time on both builds; a rebinding, an unrelated
object's `args` list and reads stay unchanged.
"""
import unittest

from test_ail_pathlib import Base

NESTED_ASSIGN = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            e.args[0] = "x"
        print(e.args)
main()
'''

NESTED_NEGATIVE = r'''def main() -> None:
    try:
        raise ValueError("a", "b")
    except ValueError as e:
        try:
            raise ValueError("c")
        except ValueError as inner:
            e.args[-1] = 7
        print(e.args)
main()
'''

NESTED_COMPUTED = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            k = 0
            e.args[k] = 3.5
        print(e.args)
main()
'''

NESTED_AUGMENTED = r'''def main() -> None:
    try:
        raise ValueError(3)
    except ValueError as e:
        try:
            raise ValueError(4)
        except ValueError as inner:
            e.args[0] += 1
        print(e.args)
main()
'''

NESTED_ANNOTATED = r'''def main() -> None:
    try:
        raise ValueError(3)
    except ValueError as e:
        try:
            raise ValueError(4)
        except ValueError as inner:
            e.args[0]: int = 5
        print(e.args)
main()
'''

NESTED_DELETE = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            del e.args[0]
        print(e.args)
main()
'''

NESTED_DESTRUCTURE = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            e.args[0], x = 1, 2
        print(e.args, x)
main()
'''

NESTED_LOOP_TARGET = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            for e.args[0] in [7]:
                pass
        print(e.args)
main()
'''

NESTED_WITH_TARGET = r'''class Ctx:
    def __enter__(self) -> int:
        return 8

    def __exit__(self, t, v, tb) -> bool:
        return False


def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            with Ctx() as e.args[0]:
                pass
        print(e.args)
main()
'''

NESTED_VALUE_ARGUMENT = r'''def main(v: str) -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            e.args[0] = v
        print(e.args)
main("x")
'''

NESTED_VALUE_LIST = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            xs = ["x"]
            e.args[0] = xs[0]
        print(e.args)
main()
'''

NESTED_VALUE_ATTRIBUTE = r'''class Box:
    def __init__(self) -> None:
        self.v = "x"


def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            b = Box()
            e.args[0] = b.v
        print(e.args)
main()
'''

NESTED_VALUE_DICT = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            d = {"v": "x"}
            e.args[0] = d["v"]
        print(e.args)
main()
'''

NESTED_ALIAS_NAME = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            x = e
            x.args[0] = "z"
        print(e.args)
main()
'''

NESTED_ALIAS_LIST = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            xs = [e]
            xs[0].args[0] = "z"
        print(e.args)
main()
'''

NESTED_ALIAS_ATTRIBUTE = r'''class Box:
    def __init__(self) -> None:
        self.e = None


def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            b = Box()
            b.e = e
            b.e.args[0] = "z"
        print(e.args)
main()
'''

NESTED_ALIAS_DICT = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            d = {"e": e}
            d["e"].args[0] = "z"
        print(e.args)
main()
'''

NESTED_ALIAS_AFTER = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            x = e
        x.args[0] = "z"
        print(e.args)
main()
'''

NESTED_SHADOW = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as e:
            e.args[0] = "x"
        print(e.args)
main()
'''

NESTED_INNER_NAME = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as err:
            err.args[0] = "x"
        print(e.args)
main()
'''

NESTED_TWO_DEEP = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as a:
            try:
                raise KeyError("c")
            except KeyError as b:
                e.args[0] = "x"
        print(e.args)
main()
'''

NESTED_EMPTY_ARGS = r'''def main() -> None:
    try:
        raise ValueError()
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            e.args[0] = "x"
        print(e.args)
main()
'''

NESTED_REBIND = r'''class Box:
    def __init__(self) -> None:
        self.args = [1, 2]


def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            e = Box()
            e.args[0] = 9
        print(e.args)
main()
'''

NESTED_UNRELATED = r'''class Box:
    def __init__(self) -> None:
        self.args = [1, 2]


def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            b = Box()
            b.args[0] = 9
        print(b.args, e.args)
main()
'''

NESTED_READ = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        try:
            raise ValueError("b")
        except ValueError as inner:
            print(e.args[0], e.args)
        print(e.args[0], e.args)
main()
'''


class Pre334Tests(Base):
    def test_nested_handler_store_is_refused(self):
        for text in (NESTED_ASSIGN, NESTED_NEGATIVE, NESTED_COMPUTED, NESTED_AUGMENTED,
                     NESTED_ANNOTATED, NESTED_DELETE, NESTED_DESTRUCTURE, NESTED_LOOP_TARGET,
                     NESTED_WITH_TARGET, NESTED_EMPTY_ARGS):
            for mode in ("typed", "gonly"):
                self.refused(text, "e.args[i]", mode=mode)

    def test_nested_handler_value_and_alias_routes_are_refused(self):
        for text in (NESTED_VALUE_ARGUMENT, NESTED_VALUE_LIST, NESTED_VALUE_ATTRIBUTE,
                     NESTED_VALUE_DICT, NESTED_ALIAS_NAME, NESTED_ALIAS_LIST,
                     NESTED_ALIAS_ATTRIBUTE, NESTED_ALIAS_DICT, NESTED_ALIAS_AFTER):
            for mode in ("typed", "gonly"):
                self.refused(text, "e.args[i]", mode=mode)

    def test_shadowing_and_deeper_nested_handlers_are_refused(self):
        for text in (NESTED_SHADOW, NESTED_INNER_NAME, NESTED_TWO_DEEP):
            self.refused(text, "e.args[i]", mode="gonly")

    def test_rebinding_inside_nested_handler_is_unchanged(self):
        self.compare("pre334_rebind_g", NESTED_REBIND, mode="gonly")

    def test_unrelated_object_is_unchanged(self):
        self.compare("pre334_unrelated_g", NESTED_UNRELATED, mode="gonly")

    def test_reading_args_in_nested_handler_is_unchanged(self):
        self.compare("pre334_read", NESTED_READ, mode="typed")
        self.compare("pre334_read_g", NESTED_READ, mode="gonly")


if __name__ == "__main__":
    unittest.main()
