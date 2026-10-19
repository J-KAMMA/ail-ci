import sys


def main() -> None:
    tokens: list[str] = sys.stdin.read().split()
    if not tokens:
        return
    n: int = int(tokens[0])
    words: list[str] = tokens[1:1 + n]
    # Length descending, then reverse alphabetical (both via reverse=True).
    words.sort(key=lambda w: (len(w), w), reverse=True)
    for word in words:
        print(word)


if __name__ == "__main__":
    main()
