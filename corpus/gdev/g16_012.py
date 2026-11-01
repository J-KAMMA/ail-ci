# task: Write a generator that yields the Collatz sequence for a starting number and find the starting value from 1 to 30 with the longest sequence.
from collections.abc import Iterator


def collatz(start: int) -> Iterator[int]:
    """Yield the Collatz sequence beginning at start and ending at 1."""
    if start < 1:
        raise ValueError("start must be a positive integer")
    n = start
    yield n
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        yield n


def main() -> None:
    best_start = 1
    best_length = 0
    for start in range(1, 31):
        length = sum(1 for _ in collatz(start))
        if length > best_length:
            best_start, best_length = start, length

    print(f"Starting value from 1 to 30 with the longest sequence: {best_start}")
    print(f"Sequence length: {best_length} terms")
    print("Sequence: " + ", ".join(str(x) for x in collatz(best_start)))


if __name__ == "__main__":
    main()
