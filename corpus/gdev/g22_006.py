# task: Extract each set bit of 0b10110100 as a separate power-of-two value and print them in ascending order.
from typing import List


def set_bit_values(n: int) -> List[int]:
    """Return each set bit of n as a separate power-of-two value, ascending."""
    values: List[int] = []
    bit_index = 0
    while (1 << bit_index) <= n:
        mask = 1 << bit_index
        if n & mask:
            values.append(mask)
        bit_index += 1
    return values


def main() -> None:
    number: int = 0b10110100
    for value in set_bit_values(number):
        print(value)


if __name__ == "__main__":
    main()
