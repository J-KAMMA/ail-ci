# task: Write a script that finds all integers from 1 to 100 that are divisible by 3 or 5 using set union of two range-derived sets.
from typing import Set


def multiples_of(divisor: int, limit: int) -> Set[int]:
    """Return the set of positive multiples of divisor that are <= limit."""
    return set(range(divisor, limit + 1, divisor))


def main() -> None:
    limit: int = 100
    by_three: Set[int] = multiples_of(3, limit)
    by_five: Set[int] = multiples_of(5, limit)
    combined: Set[int] = by_three | by_five

    result: list[int] = sorted(combined)

    print(f"Integers from 1 to {limit} divisible by 3 or 5:")
    print(result)
    print(f"Count: {len(result)}")


if __name__ == "__main__":
    main()
