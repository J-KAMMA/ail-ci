import re
import sys


def capitalise(text: str) -> str:
    """Uppercase the first letter of each sentence, leaving the rest untouched."""
    word_pattern = re.compile(r"\S+")
    pieces: list[str] = []
    cursor = 0
    at_sentence_start = True

    for match in word_pattern.finditer(text):
        pieces.append(text[cursor:match.start()])
        word = match.group()
        if at_sentence_start and word[:1].islower():
            word = word[0].upper() + word[1:]
        pieces.append(word)
        at_sentence_start = word[-1] in ".!"
        cursor = match.end()

    pieces.append(text[cursor:])
    return "".join(pieces)


def main() -> None:
    data = sys.stdin.read()
    sys.stdout.write(capitalise(data))


if __name__ == "__main__":
    main()
