# task: Use contextlib.suppress to ignore IndexError while iterating over indices of a list, then print the remaining valid elements.
from contextlib import suppress


def main() -> None:
    items: list[str] = ["alpha", "beta", "gamma", "delta"]

    # Iterate over more indices than the list actually has.
    # Out-of-range accesses raise IndexError, which is suppressed.
    indices: range = range(len(items) + 3)
    valid: list[tuple[int, str]] = []

    for i in indices:
        with suppress(IndexError):
            valid.append((i, items[i]))

    print(f"List length: {len(items)}")
    print(f"Indices checked: {len(indices)}")
    print("Valid elements:")
    for index, value in valid:
        print(f"  [{index}] {value}")

    print(f"Total valid elements: {len(valid)}")


if __name__ == "__main__":
    main()
