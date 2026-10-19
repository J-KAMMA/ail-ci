import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return
    n: int = int(data[0])
    words: list[str] = data[1 : 1 + n]

    tagged: list[tuple[int, str]] = [
        (index, f"{word}{index}")
        for index, word in enumerate(words, start=1)
    ]
    tagged.sort(key=lambda item: item[0], reverse=True)

    for _, label in tagged:
        print(label)


if __name__ == "__main__":
    main()
