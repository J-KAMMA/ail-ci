# task: Use memoized recursion to find the starting number under 30 with the longest Collatz chain and print it with its length.
from typing import Dict


def collatz_length(n: int, memo: Dict[int, int]) -> int:
    """Return the number of terms in the Collatz chain starting at n (including n and 1)."""
    if n == 1:
        return 1
    if n in memo:
        return memo[n]
    next_n = n // 2 if n % 2 == 0 else 3 * n + 1
    result = 1 + collatz_length(next_n, memo)
    memo[n] = result
    return result


def main() -> None:
    memo: Dict[int, int] = {}
    best_start = 1
    best_length = 1

    for start in range(1, 30):
        length = collatz_length(start, memo)
        if length > best_length:
            best_start = start
            best_length = length

    print(f"Starting number under 30 with the longest Collatz chain: {best_start}")
    print(f"Chain length (terms, including start and 1): {best_length}")


if __name__ == "__main__":
    main()
