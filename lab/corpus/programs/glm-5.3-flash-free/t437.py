import sys
from itertools import islice


class RunningAverage:
    def __init__(self, numbers: list[int]) -> None:
        self._numbers = numbers
        self._count = 0
        self._total = 0

    def __iter__(self) -> "RunningAverage":
        return self

    def __next__(self) -> float:
        if self._count >= len(self._numbers):
            raise StopIteration
        self._total += self._numbers[self._count]
        self._count += 1
        return self._total / self._count


def main() -> None:
    numbers = [int(token) for token in sys.stdin.readline().split()]
    if not numbers:
        return

    print(" ".join(f"{value:.2f}" for value in islice(RunningAverage(numbers), 10)))

    averages = (sum(numbers[:k]) / k for k in range(1, len(numbers) + 1))
    print(" ".join(f"{value:.2f}" for value in islice(averages, 10)))


if __name__ == "__main__":
    main()
