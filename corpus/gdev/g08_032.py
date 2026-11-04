# task: Recursively enumerate all ordered sums of 1, 2, and 3 that total 10, then print the count and the first ten sums.
from typing import Iterator


def ordered_sums(total: int, parts: tuple[int, ...] = (1, 2, 3)) -> Iterator[tuple[int, ...]]:
    """Recursively yield every ordered sum (composition) of `total` using `parts`."""
    if total == 0:
        yield ()
        return
    for part in parts:
        if part <= total:
            for rest in ordered_sums(total - part, parts):
                yield (part,) + rest


def main() -> None:
    target = 10
    all_sums = list(ordered_sums(target))
    print(f"Count: {len(all_sums)}")
    print(f"First ten sums of {target}:")
    for sums in all_sums[:10]:
        print(" + ".join(str(p) for p in sums) + f" = {target}")


if __name__ == "__main__":
    main()
