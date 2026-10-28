# task: Use itertools.chain.from_iterable to flatten a hardcoded list of lists by one level and print the combined result.
import itertools


def main() -> None:
    nested: list[list[int]] = [
        [1, 2, 3],
        [4, 5],
        [],
        [6, 7, 8, 9],
        [10],
    ]

    flattened: list[int] = list(itertools.chain.from_iterable(nested))
    print(flattened)


if __name__ == "__main__":
    main()
