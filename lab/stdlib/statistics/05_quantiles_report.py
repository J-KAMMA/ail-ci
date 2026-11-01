import statistics


def main() -> None:
    latency: list[int] = [12, 15, 11, 19, 14, 13, 18, 16, 10, 20, 17]
    print(statistics.quantiles(latency))
    print(statistics.quantiles(latency, n=10))
    print(statistics.quantiles(latency, n=4, method="inclusive"))
    small: list[int] = [3, 1, 4, 1, 5]
    print(statistics.quantiles(small, n=2))
    empty: list[int] = []
    try:
        statistics.quantiles(empty, n=4)
    except statistics.StatisticsError as exc:
        print("error:", exc)


main()
