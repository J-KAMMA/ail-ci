# task: Write a script that masks all but the last four characters of hardcoded card-number strings with asterisks and prints them.
from typing import Iterable


CARD_NUMBERS: list[str] = [
    "4539 1488 0343 6467",
    "5425-2334-3010-9903",
    "2223000048400011",
    "371449635398431",
    "6011 1111 1111 1117",
    "3530111333300000",
    "4",
    "1234",
]


def mask_card_number(number: str, visible: int = 4, mask_char: str = "*") -> str:
    """Mask all but the last `visible` alphanumeric characters of a card number.

    Separators such as spaces and dashes are preserved in their original positions.
    """
    digit_positions: list[int] = [i for i, ch in enumerate(number) if ch.isalnum()]
    total: int = len(digit_positions)
    keep_from: int = max(total - visible, 0)
    to_mask: set[int] = set(digit_positions[:keep_from])

    return "".join(
        mask_char if i in to_mask else ch for i, ch in enumerate(number)
    )


def mask_all(numbers: Iterable[str]) -> list[str]:
    """Return masked versions of every card number in the input iterable."""
    return [mask_card_number(n) for n in numbers]


def main() -> None:
    masked: list[str] = mask_all(CARD_NUMBERS)
    for original, result in zip(CARD_NUMBERS, masked):
        print(f"{original!r:24} -> {result}")


if __name__ == "__main__":
    main()
