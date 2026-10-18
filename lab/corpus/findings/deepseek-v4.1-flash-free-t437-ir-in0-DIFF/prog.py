import sys
from typing import Iterable, Iterator


class RunningAverage:
    def __init__(self, numbers: Iterable[int]) -> None:
        self._numbers = list(numbers)
        self._index = 0
        self._total = 0

    def __iter__(self) -> Iterator[float]:
        return self

    def __next__(self) -> float:
        if self._index >= len(self._numbers):
            raise StopIteration
        self._total += self._numbers[self._index]
        self._index += 1
        return self._total / self._index


def main() -> None:
    data = sys.stdin.readline().split()
    numbers = [int(x) for x in data]

    for i, avg in enumerate(RunningAverage(numbers)):
        if i >= 10:
            break
        print(f"{avg:.2f}")

    running = (sum(numbers[: i + 1]) / (i + 1) for i in range(len(numbers)))
    for i, avg in enumerate(running):
        if i >= 10:
            break
        print(f"{avg:.2f}")


if __name__ == "__main__":
    main()
