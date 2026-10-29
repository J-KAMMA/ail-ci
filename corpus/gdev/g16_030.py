# task: Implement a generator that lazily yields the first 20 Hamming (5-smooth) numbers and print them.
from collections.abc import Iterator


def hamming() -> Iterator[int]:
    """Lazily yield the Hamming (5-smooth) numbers in ascending order."""
    h: list[int] = [1]
    i2 = i3 = i5 = 0
    while True:
        yield h[-1]
        next_val = min(2 * h[i2], 3 * h[i3], 5 * h[i5])
        h.append(next_val)
        if next_val == 2 * h[i2]:
            i2 += 1
        if next_val == 3 * h[i3]:
            i3 += 1
        if next_val == 5 * h[i5]:
            i5 += 1


def main() -> None:
    gen = hamming()
    first_20: list[int] = [next(gen) for _ in range(20)]
    print(first_20)


if __name__ == "__main__":
    main()
