import sys


def reverse_words(line: str) -> str:
    """Reverse the order of the words on a line, separated by single spaces."""
    return " ".join(reversed(line.split()))


def distinct_char_count(text: str) -> int:
    """Number of distinct characters in the text, ignoring line breaks."""
    return len({ch for ch in text if ch not in "\r\n"})


def main() -> None:
    text = sys.stdin.read()
    lines = text.splitlines()

    for line in lines:
        print(reverse_words(line))

    print(distinct_char_count(text))


if __name__ == "__main__":
    main()
