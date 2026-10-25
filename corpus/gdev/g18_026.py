# task: Use itertools.pairwise over a hardcoded time series to compute consecutive differences and print the largest jump.
from itertools import pairwise


def main() -> None:
    # Hardcoded time series (e.g., daily readings)
    series: list[float] = [
        100.0,
        102.5,
        101.0,
        107.8,
        106.2,
        95.4,
        96.0,
        110.3,
        108.9,
        109.5,
    ]

    # Consecutive differences using pairwise
    diffs: list[tuple[int, float]] = []
    for index, (prev, curr) in enumerate(pairwise(series)):
        diffs.append((index, curr - prev))

    for index, delta in diffs:
        print(f"Step {index} -> {index + 1}: {series[index]:.1f} -> {series[index + 1]:.1f} (diff {delta:+.1f})")

    # Largest jump by absolute magnitude
    best_index, best_delta = max(diffs, key=lambda item: abs(item[1]))
    print(
        f"Largest jump: step {best_index} -> {best_index + 1} "
        f"from {series[best_index]:.1f} to {series[best_index + 1]:.1f} "
        f"(change {best_delta:+.1f})"
    )


if __name__ == "__main__":
    main()
