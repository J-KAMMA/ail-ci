import helper
import struct
from helper import pick
from lib.libmod import lib_fn, LIB_VALUE

TOTAL = 0
UNKNOWN = object()


def adjust(value: int) -> int:
    global TOTAL
    TOTAL = value
    return TOTAL


def outer() -> int:
    counter = 0

    def bump() -> int:
        nonlocal counter
        counter = counter + 1
        return counter

    return bump()


class Picker:
    def __init__(self, base: int) -> None:
        self.base = base

    def choose(self, left: int, right: int) -> int:
        return helper.pick(left, right)

    def twice(self, value: int) -> int:
        return self.choose(value, value)


def main() -> None:
    local = 1
    local = 2
    pair = pick(local, local)
    chosen = Picker(pair)
    method_result = chosen.twice(1)
    comp = [item * 2 for item in range(3)]
    text = "local = 99"  # local
    total = adjust(local)
    unknown_attr = UNKNOWN.value
    print(pair, method_result, comp, text, total, lib_fn(LIB_VALUE), struct.calcsize("i"))


main()
