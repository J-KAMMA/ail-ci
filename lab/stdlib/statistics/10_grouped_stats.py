import statistics


def main() -> None:
    values: list[int] = [2, 4, 4, 4, 5, 5, 7, 9]
    print(statistics.mean(values))
    print(statistics.mean(values))
    print(statistics.variance(values, xbar=5))
    print(statistics.pvariance(values, mu=5))
    print(statistics.stdev(values, xbar=5))
    print(statistics.pstdev(values, mu=5))
    print(f"{statistics.variance(values, xbar=5):.6f}")


main()
