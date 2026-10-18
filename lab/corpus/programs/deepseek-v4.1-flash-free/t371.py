import sys


def count_vowels(word: str) -> int:
    return sum(1 for ch in word if ch in "aeiou")


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    words = data[1:1 + n]
    result = sorted(words, key=lambda w: (count_vowels(w), w))
    sys.stdout.write("\n".join(result) + "\n")


if __name__ == "__main__":
    main()
