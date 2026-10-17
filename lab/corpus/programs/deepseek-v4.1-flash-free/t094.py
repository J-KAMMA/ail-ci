import sys


def main() -> None:
    data = sys.stdin.read().split("\n")
    index = 0
    while index < len(data) and data[index].strip() == "":
        index += 1
    n = int(data[index].strip())
    index += 1

    words: list[str] = []
    for _ in range(n):
        words.append(data[index].rstrip("\r\n"))
        index += 1

    for word in words:
        reversed_word = word[::-1]
        print(f"{reversed_word} {reversed_word == word}")

    print("-".join(words))


if __name__ == "__main__":
    main()
