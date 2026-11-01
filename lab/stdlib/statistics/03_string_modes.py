import statistics


def main() -> None:
    words: list[str] = "the cat the dog the bird cat".split()
    print(statistics.mode(words))
    print(statistics.multimode(words))
    colors: list[str] = ["red", "blue", "red", "green", "blue"]
    print(statistics.multimode(colors))
    empty: list[str] = []
    try:
        print(statistics.mode(empty))
    except statistics.StatisticsError as exc:
        print("error:", exc)


main()
