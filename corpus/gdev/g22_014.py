# task: Compute the Hamming weight of every byte value from 0 to 255 and print a histogram of how many bytes have each weight.
from collections import Counter


def hamming_weight(value: int) -> int:
    """Return the number of set bits in a non-negative integer."""
    count = 0
    while value:
        value &= value - 1
        count += 1
    return count


def main() -> None:
    weights: list[int] = [hamming_weight(b) for b in range(256)]
    histogram: Counter[int] = Counter(weights)

    print("Hamming weight histogram for byte values 0-255")
    print(f"{'weight':>6} {'count':>6}  bar")
    for w in range(9):
        count = histogram.get(w, 0)
        bar = "#" * count
        print(f"{w:>6} {count:>6}  {bar}")

    total = sum(histogram.values())
    print(f"total bytes: {total}")


if __name__ == "__main__":
    main()
