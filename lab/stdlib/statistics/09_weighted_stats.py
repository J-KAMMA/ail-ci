import statistics


def main() -> None:
    values: list[int] = [10, 20, 30, 40]
    weights: list[int] = [1, 2, 3, 4]
    print(statistics.fmean(values, weights=weights))
    even: list[int] = [5, 5, 5, 5]
    equal: list[int] = [1, 1, 1, 1]
    print(statistics.fmean(even, weights=equal))
    empty: list[int] = []
    try:
        statistics.fmean(empty, weights=empty)
    except statistics.StatisticsError as exc:
        print("error:", exc)


main()
