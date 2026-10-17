import sys


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    words: list[str] = data[1 : 1 + n]

    default_order: list[str] = sorted(words)
    casefold_order: list[str] = sorted(words, key=str.casefold)

    print(" ".join(default_order))
    print(" ".join(casefold_order))


if __name__ == "__main__":
    main()
