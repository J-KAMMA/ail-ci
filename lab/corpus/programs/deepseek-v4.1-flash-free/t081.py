import sys


def strip_punctuation(word: str) -> str:
    """Remove leading and trailing non-alphanumeric characters."""
    start, end = 0, len(word)
    while start < end and not word[start].isalnum():
        start += 1
    while end > start and not word[end - 1].isalnum():
        end -= 1
    return word[start:end]


def is_palindrome(word: str) -> bool:
    folded = word.casefold()
    return folded == folded[::-1]


def main() -> None:
    text = sys.stdin.read()
    palindromes = []
    for raw in text.split():
        word = strip_punctuation(raw)
        if word and is_palindrome(word):
            palindromes.append(word)

    output = [str(len(palindromes))]
    output.extend(palindromes)
    print("\n".join(output))


if __name__ == "__main__":
    main()
