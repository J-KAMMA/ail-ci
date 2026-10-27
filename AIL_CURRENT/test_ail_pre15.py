"""Pre-existing difference from CPython: an assert message keeps its own value in e.args.

`assert False, 42` constructs `AssertionError(42)` in CPython, so `e.args` is `(42,)` (and a float,
bool or str message keeps its own type too).  The typed path used to convert every numeric message
with str() before building the exception, and the general path did the same conversion for every
message; both now keep the message itself when the program reads `e.args`.
"""
from test_ail_pathlib import Base

PROGRAM = r'''
class Box:
    def __init__(self, n: int):
        self.n = n


def fail_arg(n: int) -> None:
    assert False, n


def fail_attr(b: Box) -> None:
    assert False, b.n


def fail_item(xs: list[int]) -> None:
    assert False, xs[0]


try:
    assert False, 42
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    assert False, -5
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    assert False, 9223372036854775807
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    assert False, -9223372036854775807 - 1
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    assert False, 1.5
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    assert False, True
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    assert False, False
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    assert False, ""
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    assert False, "it's"
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    fail_arg(7)
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    fail_attr(Box(8))
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))
try:
    fail_item([9])
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))


def check_dict() -> None:
    d = {"k": 10}
    try:
        assert False, d["k"]
    except AssertionError as e:
        print(repr(e.args), e.args[0], len(e.args), str(e), repr(e))


check_dict()
'''

CONTAINERS = r'''
class Box:
    def __init__(self, n: int):
        self.n = n


def fail_arg(n: int) -> None:
    assert False, n


def fail_attr(b: Box) -> None:
    assert False, b.n


def fail_item(xs: list[int]) -> None:
    assert False, xs[0]


def fail_dict(d: dict[str, int]) -> None:
    assert False, d["k"]


try:
    assert False, [1, 2]
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e))
try:
    assert False, {"a": 1}
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e))
try:
    assert False, (3, 4)
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e))
try:
    fail_arg(7)
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e))
try:
    fail_attr(Box(8))
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e))
try:
    fail_item([9])
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e))
try:
    fail_dict({"k": 10})
except AssertionError as e:
    print(repr(e.args), e.args[0], len(e.args), str(e))
'''


class Pre15AssertArgsTests(Base):
    def test_numeric_message_keeps_its_value(self):
        self.compare("pre15_assert_args", PROGRAM, mode="typed")

    def test_numeric_message_keeps_its_value_on_the_general_path(self):
        self.compare("pre15_assert_args_general", PROGRAM, mode="gonly", irs=("0",))

    def test_container_message_keeps_its_value_on_the_general_path(self):
        self.compare("pre15_assert_containers", CONTAINERS, mode="gonly", irs=("0",))
