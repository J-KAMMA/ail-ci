import sys


VOWELS = frozenset("aeiouAEIOU")


def main() -> None:
    data: bytes = sys.stdin.buffer.read()
    text: str = data.decode("utf-8", errors="replace")

    vowels: int = 0
    consonants: int = 0
    non_ascii: int = 0

    for ch in text:
        if ord(ch) > 127:
            non_ascii += 1
        elif ch in VOWELS:
            vowels += 1
        elif ch.isalpha():
            consonants += 1

    print(vowels, consonants, non_ascii)


if __name__ == "__main__":
    main()
