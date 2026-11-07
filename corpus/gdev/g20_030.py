# task: Write a script that uses re.sub with a callable to title-case only words longer than three letters in a hardcoded sentence.
import re


SENTENCE: str = (
    "the quick brown fox jumps over the lazy dog while others watch from afar, "
    "and everyone agrees it was a remarkable day for a long walk."
)

WORD_PATTERN: re.Pattern[str] = re.compile(r"\b[A-Za-z]+\b")
MIN_TITLE_LENGTH: int = 4


def title_case_long_words(match: re.Match[str]) -> str:
    """Return the matched word title-cased if it has more than three letters."""
    word: str = match.group(0)
    if len(word) >= MIN_TITLE_LENGTH:
        return word.capitalize()
    return word


def main() -> None:
    result: str = WORD_PATTERN.sub(title_case_long_words, SENTENCE)
    print(result)


if __name__ == "__main__":
    main()
