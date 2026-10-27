# task: Write a script that converts hardcoded integers from 0 to 999 into English words and prints each result.
from typing import Final

ONES: Final[list[str]] = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]

TENS: Final[list[str]] = [
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
]


def below_100(n: int) -> str:
    """Convert an integer in the range 0..99 to English words."""
    if n < 20:
        return ONES[n]
    tens, ones = divmod(n, 10)
    if ones == 0:
        return TENS[tens]
    return f"{TENS[tens]}-{ONES[ones]}"


def to_words(n: int) -> str:
    """Convert an integer in the range 0..999 to English words."""
    if not 0 <= n <= 999:
        raise ValueError(f"number out of range: {n}")
    if n < 100:
        return below_100(n)
    hundreds, rest = divmod(n, 100)
    head = f"{ONES[hundreds]} hundred"
    if rest == 0:
        return head
    return f"{head} and {below_100(rest)}"


def main() -> None:
    for number in range(1000):
        print(f"{number}: {to_words(number)}")


if __name__ == "__main__":
    main()
