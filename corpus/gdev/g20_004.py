# task: Write a script that uses re.finditer to locate every occurrence of a repeated word (like 'the the') in a hardcoded paragraph and prints each match with its start index.
import re
from typing import Final

PARAGRAPH: Final[str] = (
    "The quick brown fox jumped over the the lazy dog while the sun was was "
    "setting behind the hills. She said that that idea was good, but we we "
    "needed more time. He walked to to the store and bought bread. "
    "The theater was empty, and and the actors waited for for the audience. "
    "This is is a test of the the detection system. Their their plan worked "
    "well, and the the results were clear. Nothing repeated here: cat dog bird."
)

REPEATED_WORD: Final[re.Pattern[str]] = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)


def main() -> None:
    matches: list[re.Match[str]] = list(REPEATED_WORD.finditer(PARAGRAPH))
    print(f"Found {len(matches)} repeated-word occurrence(s):")
    for match in matches:
        print(f"start={match.start():4d}  match={match.group(0)!r}  word={match.group(1)!r}")


if __name__ == "__main__":
    main()
