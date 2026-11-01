# task: Compute the sum of all numbers below one million that are palindromic in both base 10 and base 2.
from typing import Iterator


def is_palindrome_str(s: str) -> bool:
    return s == s[::-1]


def is_double_base_palindrome(n: int) -> bool:
    return is_palindrome_str(str(n)) and is_palindrome_str(bin(n)[2:])


def double_base_palindromes_below(limit: int) -> Iterator[int]:
    for n in range(1, limit):
        if is_double_base_palindrome(n):
            yield n


def main() -> None:
    limit: int = 1_000_000
    values: list[int] = list(double_base_palindromes_below(limit))
    total: int = sum(values)
    print(f"Count: {len(values)}")
    print(f"Sum: {total}")


if __name__ == "__main__":
    main()
