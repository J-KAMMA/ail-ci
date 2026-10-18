import sys
from bisect import bisect_left


def main() -> None:
    data = sys.stdin.read().split()
    numbers: list[int] = [int(token) for token in data]

    sorted_numbers: list[int] = sorted(numbers)

    counts: list[int] = [bisect_left(sorted_numbers, value) for value in numbers]
    zero_insertion_point: int = bisect_left(sorted_numbers, 0)

    print(" ".join(str(count) for count in counts))
    print(zero_insertion_point)


if __name__ == "__main__":
    main()
