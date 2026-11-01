import statistics


def main() -> None:
    temps: list[float] = [12.5, 15.0, 11.25, 18.75, 14.5, 13.0]
    print(statistics.fmean(temps))
    print(statistics.median(temps))
    print(statistics.median_low(temps))
    print(statistics.median_high(temps))
    print(statistics.mode(temps))
    print(statistics.multimode(temps))
    print(f"{statistics.fmean(temps):.3f}")
    readings: list[float] = [1.5, 2.5, 2.5, 3.5]
    print(statistics.median(readings), statistics.mode(readings))


main()
