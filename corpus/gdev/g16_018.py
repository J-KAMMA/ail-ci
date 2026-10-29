# task: Use zip with itertools.cycle to pair a repeating list of labels with seven numbers and print the resulting pairs.
from itertools import cycle


def main() -> None:
    labels: list[str] = ["alpha", "beta", "gamma"]
    numbers: list[int] = [1, 2, 3, 4, 5, 6, 7]

    pairs: list[tuple[str, int]] = list(zip(cycle(labels), numbers))

    for label, number in pairs:
        print(f"({label!r}, {number})")


if __name__ == "__main__":
    main()
