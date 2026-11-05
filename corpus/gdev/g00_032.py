# task: Write a script that converts a hardcoded list of decimal integers to 8-bit zero-padded binary strings and prints them.
from typing import Sequence


DECIMAL_VALUES: list[int] = [0, 1, 2, 5, 10, 42, 127, 128, 200, 255]


def to_8bit_binary(value: int) -> str:
    """Convert an integer in the range 0-255 to an 8-bit zero-padded binary string."""
    if not 0 <= value <= 255:
        raise ValueError(f"value out of 8-bit range: {value}")
    return format(value, "08b")


def convert_all(values: Sequence[int]) -> list[str]:
    """Convert each decimal integer in values to an 8-bit binary string."""
    return [to_8bit_binary(v) for v in values]


def main() -> None:
    binaries = convert_all(DECIMAL_VALUES)
    for decimal, binary in zip(DECIMAL_VALUES, binaries):
        print(f"{decimal:>3} -> {binary}")


if __name__ == "__main__":
    main()
