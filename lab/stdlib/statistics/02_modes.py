import statistics


def main() -> None:
    votes: list[int] = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    print(statistics.mode(votes))
    print(statistics.multimode(votes))
    tied: list[int] = [2, 2, 7, 7, 9]
    print(statistics.mode(tied))
    print(statistics.multimode(tied))
    print(statistics.median_low(tied), statistics.median_high(tied))
    single: list[int] = [42]
    print(statistics.mode(single), statistics.multimode(single))


main()
