import sys
from collections import deque


def main() -> None:
    window: deque[int] = deque(maxlen=5)
    for token in sys.stdin.read().split():
        window.append(int(token))
        window.rotate(1)
        print(window)
    print(sum(window))


if __name__ == "__main__":
    main()
