import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    words = data[1:1 + n]
    default_order = sorted(words)
    casefold_order = sorted(words, key=str.casefold)
    print(" ".join(default_order))
    print(" ".join(casefold_order))


if __name__ == "__main__":
    main()
