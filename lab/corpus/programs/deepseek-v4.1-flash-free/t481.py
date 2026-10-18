import sys
from collections import deque
from typing import Deque


def main() -> None:
    data = sys.stdin.read().split()
    numbers = [int(token) for token in data]

    window: Deque[int] = deque(maxlen=5)
    for number in numbers:
        window.append(number)
        window.rotate(1)
        print(window)

    print(sum(window))


if __name__ == "__main__":
    main()
