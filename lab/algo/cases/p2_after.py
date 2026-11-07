from collections import deque

LIMIT = 150000


def main() -> None:
    values = deque(range(LIMIT))
    total = 0
    for _ in range(LIMIT):
        total += values.popleft()
    print(total, len(values))


main()
