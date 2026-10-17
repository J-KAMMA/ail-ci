import sys


def main() -> None:
    words = sys.stdin.read().split()
    if not words:
        return

    print(", ".join(words))

    if len(words) == 1:
        print(words[0])
    else:
        print(", ".join(words[:-1]) + " and " + words[-1])

    width = max(len(word) for word in words)
    for word in words:
        print(word.rjust(width))


if __name__ == "__main__":
    main()
