import sys


def digit_sum(value: int) -> int:
    """Return the sum of the decimal digits of a non-negative integer."""
    return sum(int(ch) for ch in str(value))


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    n = int(data[0])
    numbers = [int(token) for token in data[1:1 + n]]

    best: int | None = None
    best_key: tuple[int, int] | None = None

    for value in numbers:
        if value < 0:
            continue
        # Larger digit sum wins; on ties, the smaller number wins.
        key = (digit_sum(value), -value)
        if best_key is None or key > best_key:
            best_key = key
            best = value

    if best is not None:
        print(best)


if __name__ == "__main__":
    main()
