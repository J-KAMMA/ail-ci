"""Small formatting and sorting helpers built with functools.partial."""
from functools import partial


def label(prefix, value, width=8):
    return f"{prefix}{value:>{width}}"


def by_field(index, row):
    return row[index]


def scale(factor, value):
    return value * factor


def clamp(value, low=0, high=100):
    if value < low:
        return low
    if value > high:
        return high
    return value


def main() -> None:
    money = partial(label, "amount=", width=6)
    count = partial(label, "count=")
    print(money(42))
    print(money(7))
    print(count(1234))

    rows = [("pear", 4), ("apple", 9), ("fig", 6), ("kiwi", 2)]
    print(sorted(rows, key=partial(by_field, 1)))
    print(sorted(rows, key=partial(by_field, 0)))

    doubled = list(map(partial(scale, 2), [1, 2, 3, 4]))
    print(doubled)
    print(list(map(partial(clamp, low=10), [-5, 3, 12, 200])))
    print(list(map(partial(clamp, low=10, high=20), [1, 15, 30])))


main()
