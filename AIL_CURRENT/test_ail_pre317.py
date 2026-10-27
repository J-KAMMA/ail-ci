"""pre317: storing into a caught exception's e.args[i] is refused by name.

CPython raises TypeError for `e.args[0] = ...` (e.args is a tuple) and prints a traceback AIL does
not model; the statement now fails at compile time on both builds instead of running with a
different stderr traceback.
"""
import unittest

from test_ail_pathlib import Base

ASSIGN = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        e.args[0] = "x"
        print(e.args)
main()
'''

NEGATIVE = r'''def main() -> None:
    try:
        raise ValueError("a", "b")
    except ValueError as e:
        e.args[-1] = 7
        print(e.args)
main()
'''

COMPUTED = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        k = 0
        e.args[k] = 3.5
        print(e.args)
main()
'''

AUGMENTED = r'''def main() -> None:
    try:
        raise ValueError(3)
    except ValueError as e:
        e.args[0] += 1
        print(e.args)
main()
'''

ANNOTATED = r'''def main() -> None:
    try:
        raise ValueError(3)
    except ValueError as e:
        e.args[0]: int = 5
        print(e.args)
main()
'''

DELETE = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        del e.args[0]
        print(e.args)
main()
'''

DESTRUCTURE = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        e.args[0], x = 1, 2
        print(e.args, x)
main()
'''

LOOP_TARGET = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        for e.args[0] in [7]:
            pass
        print(e.args)
main()
'''

WITH_TARGET = r'''class Ctx:
    def __enter__(self) -> int:
        return 8

    def __exit__(self, t, v, tb) -> bool:
        return False


def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        with Ctx() as e.args[0]:
            pass
        print(e.args)
main()
'''

ALIAS_NAME = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        x = e
        x.args[0] = "z"
        print(e.args)
main()
'''

ALIAS_LIST = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        xs = [e]
        xs[0].args[0] = "z"
        print(e.args)
main()
'''

ALIAS_ATTRIBUTE = r'''class Box:
    def __init__(self) -> None:
        self.e = None


def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        b = Box()
        b.e = e
        b.e.args[0] = "z"
        print(e.args)
main()
'''

ALIAS_DICT = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        d = {"e": e}
        d["e"].args[0] = "z"
        print(e.args)
main()
'''

VALUE_ARGUMENT = r'''def main(v: str) -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        e.args[0] = v
        print(e.args)
main("x")
'''

VALUE_LIST = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        xs = ["x"]
        e.args[0] = xs[0]
        print(e.args)
main()
'''

VALUE_ATTRIBUTE = r'''class Box:
    def __init__(self) -> None:
        self.v = "x"


def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        b = Box()
        e.args[0] = b.v
        print(e.args)
main()
'''

VALUE_DICT = r'''def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        d = {"v": "x"}
        e.args[0] = d["v"]
        print(e.args)
main()
'''

REBIND_HANDLER = r'''class Box:
    def __init__(self) -> None:
        self.args = [1, 2]


def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        e = Box()
        e.args[0] = 9
        print(e.args)
main()
'''

USER_OBJECT = r'''class Box:
    def __init__(self) -> None:
        self.args = [1, 2]


def main() -> None:
    try:
        raise ValueError("a")
    except ValueError as e:
        b = Box()
        b.args[0] = 9
        print(b.args, e.args)
main()
'''

NESTED_ITEM = r'''class Cell:
    def __init__(self) -> None:
        self.x = 1


def main() -> None:
    try:
        raise ValueError(Cell())
    except ValueError as e:
        e.args[0].x = 5
        print(e.args[0].x)
main()
'''


class Pre317Tests(Base):
    def test_storing_into_exception_args_is_refused(self):
        for text in (ASSIGN, NEGATIVE, COMPUTED, AUGMENTED, ANNOTATED, DELETE, DESTRUCTURE,
                     LOOP_TARGET, WITH_TARGET):
            for mode in ("typed", "gonly"):
                self.refused(text, "e.args[i]", mode=mode)

    def test_value_routes_are_refused(self):
        for text in (VALUE_ARGUMENT, VALUE_LIST, VALUE_ATTRIBUTE, VALUE_DICT,
                     ALIAS_NAME, ALIAS_LIST, ALIAS_ATTRIBUTE, ALIAS_DICT):
            for mode in ("typed", "gonly"):
                self.refused(text, "e.args[i]", mode=mode)

    def test_another_objects_args_list_is_unchanged(self):
        self.compare("pre317_user_object", USER_OBJECT, mode="typed")
        self.compare("pre317_user_object_g", USER_OBJECT, mode="gonly")

    def test_rebinding_the_handler_name_is_unchanged(self):
        self.compare("pre317_rebind_handler_g", REBIND_HANDLER, mode="gonly")

    def test_storing_inside_the_argument_object_is_unchanged(self):
        self.compare("pre317_nested_item_g", NESTED_ITEM, mode="gonly")


if __name__ == "__main__":
    unittest.main()
