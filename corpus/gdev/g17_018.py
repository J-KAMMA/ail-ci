# task: Use functools.singledispatch to describe different Python value types and apply the function across a mixed list.
from functools import singledispatch
from typing import Any
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction


@singledispatch
def describe(value: Any) -> str:
    """Fallback for any type without a specific registration."""
    return f"object of type {type(value).__name__}: {value!r}"


@describe.register
def _(value: bool) -> str:
    # bool must be registered separately because bool is a subclass of int.
    return f"bool {'True' if value else 'False'}"


@describe.register
def _(value: int) -> str:
    kind = "even" if value % 2 == 0 else "odd"
    return f"int {value} ({kind})"


@describe.register
def _(value: float) -> str:
    return f"float {value:.3f}"


@describe.register
def _(value: complex) -> str:
    return f"complex real={value.real} imag={value.imag}"


@describe.register
def _(value: Decimal) -> str:
    return f"Decimal {value} (exact)"


@describe.register
def _(value: Fraction) -> str:
    return f"Fraction {value.numerator}/{value.denominator}"


@describe.register
def _(value: str) -> str:
    return f"str of length {len(value)}: {value!r}"


@describe.register
def _(value: bytes) -> str:
    return f"bytes of length {len(value)}: {value.hex()}"


@describe.register
def _(value: bytearray) -> str:
    return f"bytearray of length {len(value)}"


@describe.register
def _(value: datetime) -> str:
    return f"datetime {value.isoformat()}"


@describe.register
def _(value: date) -> str:
    return f"date {value.isoformat()}"


@describe.register
def _(value: list) -> str:
    inner = ", ".join(describe(item) for item in value)
    return f"list[{len(value)}] [{inner}]"


@describe.register
def _(value: tuple) -> str:
    inner = ", ".join(describe(item) for item in value)
    return f"tuple[{len(value)}] ({inner})"


@describe.register
def _(value: set) -> str:
    # Sort items by their description so output does not depend on set order.
    parts = sorted(describe(item) for item in value)
    return f"set[{len(value)}] {{{'; '.join(parts)}}}"


@describe.register
def _(value: frozenset) -> str:
    parts = sorted(describe(item) for item in value)
    return f"frozenset[{len(value)}] {{{'; '.join(parts)}}}"


@describe.register
def _(value: dict) -> str:
    items = [f"{describe(k)} => {describe(v)}" for k, v in value.items()]
    return f"dict[{len(value)}] {{{'; '.join(items)}}}"


@describe.register
def _(value: OrderedDict) -> str:
    items = [f"{describe(k)} => {describe(v)}" for k, v in value.items()]
    return f"OrderedDict[{len(value)}] {{{'; '.join(items)}}}"


@describe.register
def _(value: type) -> str:
    return f"type {value.__module__}.{value.__qualname__}"


@describe.register
def _(value: None.__class__) -> str:
    return "NoneType None"


def main() -> None:
    mixed: list[Any] = [
        42,
        7,
        True,
        3.14159,
        2 + 3j,
        Decimal("1.10"),
        Fraction(3, 4),
        "hello",
        b"\x01\xff",
        bytearray(b"abc"),
        date(2024, 2, 29),
        datetime(2024, 1, 15, 9, 30, 0),
        [1, "two", 3.0],
        (4, None),
        {5, 6},
        frozenset({"x"}),
        {"key": [1, 2], "other": (True,)},
        OrderedDict([("a", 1), ("b", 2)]),
        int,
        None,
        range(3),
    ]

    for index, item in enumerate(mixed):
        print(f"{index:2d}: {describe(item)}")


if __name__ == "__main__":
    main()
