# task: Recursively generate all 3-element combinations of the numbers 1 through 6 without using itertools and print them.
from typing import List


def generate_combinations(items: List[int], k: int, start: int = 0) -> List[List[int]]:
    """Recursively generate all k-element combinations of items, in lexicographic order."""
    if k == 0:
        return [[]]
    if start >= len(items):
        return []
    result: List[List[int]] = []
    # Choose items[start] and combine with the rest
    for combo in generate_combinations(items, k - 1, start + 1):
        result.append([items[start]] + combo)
    # Skip items[start] and continue
    result.extend(generate_combinations(items, k, start + 1))
    return result


def main() -> None:
    numbers: List[int] = [1, 2, 3, 4, 5, 6]
    combinations: List[List[int]] = generate_combinations(numbers, 3)
    for combo in combinations:
        print(tuple(combo))


if __name__ == "__main__":
    main()
