# task: Compute the first 15 Catalan numbers with dynamic programming and print them as a list.
from typing import List


def catalan_numbers(count: int) -> List[int]:
    """Return the first `count` Catalan numbers using dynamic programming.

    Uses the recurrence C(0) = 1 and C(n) = sum_{i=0}^{n-1} C(i) * C(n-1-i).
    """
    if count <= 0:
        return []
    table: List[int] = [0] * count
    table[0] = 1
    for n in range(1, count):
        total = 0
        for i in range(n):
            total += table[i] * table[n - 1 - i]
        table[n] = total
    return table


def main() -> None:
    result: List[int] = catalan_numbers(15)
    print(result)


if __name__ == "__main__":
    main()
