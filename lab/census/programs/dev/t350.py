import sys


def collatz_length(start: int, cache: dict[int, int]) -> int:
    """Return the number of terms in the Collatz chain from start down to 1, inclusive."""
    path: list[int] = []
    x = start
    while x not in cache:
        path.append(x)
        x = x // 2 if x % 2 == 0 else 3 * x + 1

    length = cache[x]
    for value in reversed(path):
        length += 1
        cache[value] = length
    return cache[start]


def main() -> None:
    data = sys.stdin.readline().strip()
    n = int(data)
    limit = n * 100

    cache: dict[int, int] = {1: 1}
    best_start = 1
    best_len = 1

    for start in range(1, limit):
        length = collatz_length(start, cache)
        if length > best_len:
            best_len = length
            best_start = start

    print(f"{best_start} {best_len}")


if __name__ == "__main__":
    main()
