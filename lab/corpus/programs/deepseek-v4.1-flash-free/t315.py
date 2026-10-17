import sys


def max_non_adjacent_sum(values: list[int]) -> int:
    empty_prev2: int = 0
    empty_prev1: int = 0
    best: int | None = None
    for value in values:
        with_value = empty_prev2 + value
        best = with_value if best is None else max(best, with_value)
        empty_prev2, empty_prev1 = empty_prev1, max(empty_prev1, with_value)
    return best if best is not None else 0


def main() -> None:
    data = sys.stdin.read().split()
    values = [int(token) for token in data]
    print(max_non_adjacent_sum(values))


if __name__ == "__main__":
    main()
