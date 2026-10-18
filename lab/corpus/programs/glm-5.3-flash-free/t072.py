import sys

PUNCTUATION = ",.!;"


def contains_target_word(line: str) -> bool:
    """Return True if the line contains 'a' or 'e' as a whole word."""
    for word in line.split():
        if word.rstrip(PUNCTUATION) in ("a", "e"):
            return True
    return False


def main() -> None:
    for number, line in enumerate(sys.stdin.read().splitlines(), start=1):
        if contains_target_word(line):
            print(f"{number}: {line}")


if __name__ == "__main__":
    main()
