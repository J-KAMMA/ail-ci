import sys


def longest_word(words: list[str]) -> str:
    return max(words, key=len)


def process_line(line: str) -> str:
    words = line.split()
    if not words:
        return "-"
    longest = longest_word(words)
    return f"{len(line)} {len(longest)} {longest}"


def main() -> None:
    text = sys.stdin.read()
    for line in text.splitlines():
        print(process_line(line))


if __name__ == "__main__":
    main()
