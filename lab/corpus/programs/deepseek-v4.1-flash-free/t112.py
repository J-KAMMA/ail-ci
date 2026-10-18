import sys


def remove_consecutive_duplicates(text: str) -> str:
    result: list[str] = []
    for char in text:
        if not result or result[-1] != char:
            result.append(char)
    return "".join(result)


def main() -> None:
    line = sys.stdin.readline().rstrip("\n")
    words = line.split()

    before = " ".join(words)
    after = " ".join(remove_consecutive_duplicates(word) for word in words)

    print(after)
    print(len(before))
    print(len(after))


if __name__ == "__main__":
    main()
