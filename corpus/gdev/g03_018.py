# task: Compute the z-score of each element in a fixed list of floats and print the scores rounded to four decimals.
import statistics


DATA: list[float] = [2.5, 3.7, 1.2, 9.8, 4.4, 6.1, 5.0, 7.3]


def z_scores(values: list[float]) -> list[float]:
    """Return the z-score of each value using the population standard deviation.

    If all values are identical (standard deviation is zero), every z-score is 0.0.
    """
    mean: float = statistics.fmean(values)
    sd: float = statistics.pstdev(values)
    if sd == 0:
        return [0.0 for _ in values]
    return [(v - mean) / sd for v in values]


def main() -> None:
    scores: list[float] = z_scores(DATA)
    for value, score in zip(DATA, scores):
        # Adding 0.0 converts a negative zero after rounding into a plain 0.0.
        print(f"value={value:.4f} z={round(score, 4) + 0.0:.4f}")


if __name__ == "__main__":
    main()
