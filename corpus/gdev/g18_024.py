# task: Use itertools.starmap with hardcoded argument tuples to compute powers and print the results.
import itertools
import operator


def main() -> None:
    # Hardcoded (base, exponent) argument tuples.
    pairs: list[tuple[int, int]] = [
        (2, 0),
        (2, 1),
        (2, 10),
        (3, 4),
        (5, 3),
        (7, 2),
        (10, 6),
        (-2, 5),
        (-3, 4),
        (2, 64),
    ]

    results: list[int | float] = list(itertools.starmap(operator.pow, pairs))

    print("Powers computed with itertools.starmap:")
    for (base, exponent), value in zip(pairs, results):
        print(f"{base}^{exponent} = {value}")

    total: int = sum(results)  # type: ignore[arg-type]
    print(f"Sum of all results: {total}")


if __name__ == "__main__":
    main()
