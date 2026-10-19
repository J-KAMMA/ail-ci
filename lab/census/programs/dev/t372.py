import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    words: list[str] = data[1:1 + n]

    def last_letter_key(word: str) -> str:
        return word.lower()[-1:]

    for word in sorted(words, key=last_letter_key):
        print(word)


if __name__ == "__main__":
    main()
