# task: Use a generator to find all perfect squares below 500 that are palindromes and print them.
from collections.abc import Iterator


def perfect_squares_below(limit: int) -> Iterator[int]:
    """Yield positive perfect squares strictly less than limit."""
    n = 1
    while n * n < limit:
        yield n * n
        n += 1


def is_palindrome(value: int) -> bool:
    """Return True if the decimal representation of value reads the same both ways."""
    text = str(value)
    return text == text[::-1]


def palindromic_squares_below(limit: int) -> Iterator[int]:
    """Yield perfect squares below limit whose decimal digits form a palindrome."""
    for square in perfect_squares_below(limit):
        if is_palindrome(square):
            yield square


def main() -> None:
    for value in palindromic_squares_below(500):
        print(value)


if __name__ == "__main__":
    main()
