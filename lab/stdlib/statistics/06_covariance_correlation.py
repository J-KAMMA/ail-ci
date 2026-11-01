import statistics


def main() -> None:
    hours: list[int] = [1, 2, 3, 4, 5, 6, 7, 8]
    errors: list[int] = [3, 2, 4, 3, 5, 6, 6, 8]
    print(statistics.covariance(hours, errors))
    print(statistics.correlation(hours, errors, method="linear"))
    print(f"{statistics.correlation(hours, errors):.4f}")
    same: list[int] = [4, 4, 4, 4]
    try:
        print(statistics.correlation(same, errors))
    except statistics.StatisticsError as exc:
        print("error:", exc)
    short: list[int] = [1, 2, 3]
    try:
        statistics.covariance(hours, short)
    except statistics.StatisticsError as exc:
        print("error:", exc)


main()
