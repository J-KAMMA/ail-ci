# task: Write a script that partitions a hardcoded list into even and odd numbers and prints both resulting lists.
from typing import List, Tuple


def partition_even_odd(numbers: List[int]) -> Tuple[List[int], List[int]]:
    evens: List[int] = []
    odds: List[int] = []
    for n in numbers:
        if n % 2 == 0:
            evens.append(n)
        else:
            odds.append(n)
    return evens, odds


def main() -> None:
    numbers: List[int] = [12, 7, 3, 18, 25, 0, 42, 9, 16, -4, 11, 8]
    evens, odds = partition_even_odd(numbers)
    print("Even numbers:", evens)
    print("Odd numbers:", odds)


if __name__ == "__main__":
    main()
