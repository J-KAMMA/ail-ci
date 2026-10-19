import sys
import unicodedata


def is_punct(ch: str) -> bool:
    """Return True if the character is a Unicode punctuation character."""
    return unicodedata.category(ch).startswith("P")


def clean_token(token: str) -> str:
    """Strip leading and trailing punctuation from a token."""
    start = 0
    end = len(token)
    while start < end and is_punct(token[start]):
        start += 1
    while end > start and is_punct(token[end - 1]):
        end -= 1
    return token[start:end]


def main() -> None:
    text = sys.stdin.read()
    words: set[str] = set()
    for token in text.split():
        word = clean_token(token)
        if word:
            words.add(word)

    out_lines = []
    for word in sorted(words):
        out_lines.append(f"{word} {ord(word[0]):04X}")

    if out_lines:
        sys.stdout.write("\n".join(out_lines) + "\n")


if __name__ == "__main__":
    main()
