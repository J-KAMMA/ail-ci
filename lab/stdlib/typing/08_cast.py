from typing import Any, cast


def as_int(value: Any) -> int:
    return cast(int, value)


def as_text(value: Any) -> str:
    return cast(str, value)


def parse_pair(raw: Any) -> int:
    first = cast(int, raw[0])
    second = cast(int, raw[1])
    return first * 10 + second


def main() -> None:
    print(as_int(12))
    print(as_text("hello"))
    print(parse_pair((3, 4)))
    values: list[Any] = [1, "two", 3.5]
    print(as_int(values[0]))
    print(as_text(values[1]))
    print(cast(float, values[2]) + 0.5)
    text = cast(str, as_text(7))
    print(text * 2)


main()
