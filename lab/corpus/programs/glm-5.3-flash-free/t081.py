import sys
import unicodedata


def strip_punctuation(word: str) -> str:
    start = 0
    end = len(word)
    while start < end and unicodedata.category(word[start]).startswith("P"):
        start += 1
    while end > start and unicodedata.category(word[end - 1]).startswith("P"):
        end -= 1
    return word[start:end]


def is_palindrome(word: str) -> bool:
    folded = word.casefold()
    return len(folded) > 0 and folded == folded[::-1]


def main() -> None:
    words = sys.stdin.read().split()
    cleaned = [strip_punctuation(w) for w in words]
    palindromes = [w for w in cleaned if is_palindrome(w)]
    print(len(palindromes))
    for p in palindromes:
        print(p)


if __name__ == "__main__":
    main()
