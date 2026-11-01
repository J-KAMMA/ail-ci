import statistics


def main() -> None:
    x: list[int] = [1, 2, 3, 4, 5]
    y: list[int] = [3, 5, 7, 9, 11]
    fit = statistics.linear_regression(x, y)
    print(fit)
    print(fit.slope)
    print(fit.intercept)
    prop = statistics.linear_regression(x, y, proportional=True)
    print(prop)
    short: list[int] = [1]
    try:
        statistics.linear_regression(x, short)
    except statistics.StatisticsError as exc:
        print("error:", exc)


main()
