# task: Write a script that computes a sliding window sum of size 3 over a fixed list of numbers and prints each window sum.
from typing import Sequence


def sliding_window_sums(values: Sequence[int], window_size: int) -> list[int]:
    """Return the sum of each contiguous window of the given size."""
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    sums: list[int] = []
    current = sum(values[:window_size])
    if len(values) < window_size:
        return sums
    sums.append(current)
    for i in range(window_size, len(values)):
        current += values[i] - values[i - window_size]
        sums.append(current)
    return sums


def main() -> None:
    numbers: list[int] = [4, 8, 15, 16, 23, 42, 7, 1, 9, 12]
    window_size: int = 3
    sums = sliding_window_sums(numbers, window_size)
    for index, window_sum in enumerate(sums):
        window = numbers[index:index + window_size]
        print(f"Window {index}: {window} -> sum = {window_sum}")


if __name__ == "__main__":
    main()
