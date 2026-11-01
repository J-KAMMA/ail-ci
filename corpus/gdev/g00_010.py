# task: Write a script that converts a hardcoded string into title case while keeping small words like 'and' and 'of' lowercase unless they begin the title.
import re
from typing import Final

SMALL_WORDS: Final[frozenset[str]] = frozenset({
    "a", "an", "and", "as", "at", "but", "by", "en", "for", "if",
    "in", "of", "on", "or", "the", "to", "v", "via", "vs", "nor",
    "from", "into", "with",
})

WORD_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")

SOURCE_TEXT: Final[str] = (
    "the lord of the rings and a tale of an ODD journey: "
    "from the shire to mordor, as told by the hobbit"
)


def title_case(text: str) -> str:
    """Return text in title case, keeping small words lowercase unless first."""
    matches = list(WORD_RE.finditer(text))
    pieces: list[str] = []
    last_end = 0

    for index, match in enumerate(matches):
        word = match.group(0)
        if index == 0 or word.lower() not in SMALL_WORDS:
            cased = word[:1].upper() + word[1:].lower()
        else:
            cased = word.lower()

        pieces.append(text[last_end:match.start()])
        pieces.append(cased)
        last_end = match.end()

    pieces.append(text[last_end:])
    return "".join(pieces)


def main() -> None:
    print(title_case(SOURCE_TEXT))


if __name__ == "__main__":
    main()
