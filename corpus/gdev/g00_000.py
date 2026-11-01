# task: Write a script that reverses each word in a hardcoded sentence while keeping the word order, and prints the result.
def reverse_word(word: str) -> str:
    return word[::-1]


def reverse_each_word(sentence: str) -> str:
    return " ".join(reverse_word(word) for word in sentence.split())


def main() -> None:
    sentence: str = "The quick brown fox jumps over the lazy dog"
    print(reverse_each_word(sentence))


if __name__ == "__main__":
    main()
