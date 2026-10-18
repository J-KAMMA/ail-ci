import sys
import string

_PUNCTUATION_TABLE = str.maketrans("", "", string.punctuation)


def remove_punctuation(text: str) -> str:
    return text.translate(_PUNCTUATION_TABLE)


def count_letters_and_digits(text: str) -> tuple[int, int]:
    letters = sum(ch in string.ascii_letters for ch in text)
    digits = sum(ch in string.digits for ch in text)
    return letters, digits


def main() -> None:
    text = sys.stdin.read()
    cleaned = remove_punctuation(text)
    letters, digits = count_letters_and_digits(cleaned)

    print(cleaned, end="")
    print(f"letters: {letters}")
    print(f"digits: {digits}")


if __name__ == "__main__":
    main()
