import statistics


def main() -> None:
    scores: list[int] = [72, 85, 91, 66, 78, 85, 93, 70, 88, 79]
    print("count", len(scores))
    print("mean", statistics.mean(scores))
    print("fmean", statistics.fmean(scores))
    print("median", statistics.median(scores))
    print("median_low", statistics.median_low(scores))
    print("median_high", statistics.median_high(scores))
    print("variance", statistics.variance(scores))
    print("pvariance", statistics.pvariance(scores))
    print("stdev", f"{statistics.stdev(scores):.4f}")
    print("pstdev", f"{statistics.pstdev(scores):.4f}")


main()
