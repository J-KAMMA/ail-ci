# task: Compute the parity of every integer from 0 to 255 using XOR folding and print how many have odd parity.
from typing import Final


TOTAL: Final[int] = 256


def parity_xor_fold(value: int) -> int:
    """Return 1 if the number of set bits in value is odd, else 0, using XOR folding."""
    value ^= value >> 4
    value ^= value >> 2
    value ^= value >> 1
    return value & 1


def main() -> None:
    odd_count: int = 0
    for number in range(TOTAL):
        if parity_xor_fold(number) == 1:
            odd_count += 1
    print(f"Numbers with odd parity in 0..255: {odd_count}")


if __name__ == "__main__":
    main()
