import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    n = int(data[0])
    words = data[1:1 + n]

    suffixed = [(f"{word}{index}", index) for index, word in enumerate(words, start=1)]
    suffixed.sort(key=lambda pair: pair[1], reverse=True)

    sys.stdout.write("\n".join(token for token, _ in suffixed) + "\n")


if __name__ == "__main__":
    main()
