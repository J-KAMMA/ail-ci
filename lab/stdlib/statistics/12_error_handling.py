import statistics


def main() -> None:
    empty: list[int] = []
    one: list[int] = [7]
    try:
        print(statistics.mean(empty))
    except statistics.StatisticsError as exc:
        print("mean:", exc)
    try:
        print(statistics.variance(one))
    except statistics.StatisticsError as exc:
        print("variance:", exc)
    try:
        print(statistics.median(empty))
    except statistics.StatisticsError as exc:
        print("median:", exc)
    try:
        print(statistics.stdev(one))
    except statistics.StatisticsError as exc:
        print("stdev:", exc)
    try:
        print(statistics.mode(empty))
    except statistics.StatisticsError as exc:
        print("mode:", exc)


main()
