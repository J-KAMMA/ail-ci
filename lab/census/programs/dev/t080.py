import sys
import unicodedata


def strip_punctuation(token: str) -> str:
    """Remove leading and trailing Unicode punctuation characters from a token."""
    start = 0
    end = len(token)
    while start < end and unicodedata.category(token[start]).startswith("P"):
        start += 1
    while end > start and unicodedata.category(token[end - 1]).startswith("P"):
        end -= 1
    return token[start:end]


def main() -> None:
    text = sys.stdin.read()
    words: list[str] = []
    for token in text.split():
        word = strip_punctuation(token)
        if word:
            words.append(word)

    if not words:
        return

    longest_chars = words[0]
    longest_bytes = words[0]
    for word in words[1:]:
        if len(word) > len(longest_chars):
            longest_chars = word
        if len(word.encode("utf-8")) > len(longest_bytes.encode("utf-8")):
            longest_bytes = word

    print(f"{longest_chars} {len(longest_chars)}")
    print(f"{longest_bytes} {len(longest_bytes.encode('utf-8'))}")


if __name__ == "__main__":
    main()
