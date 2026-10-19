import sys


def main() -> None:
    data = sys.stdin.read().split("\n")
    n = int(data[0].strip())
    words: list[str] = []
    for i in range(1, n + 1):
        line = data[i] if i < len(data) else ""
        words.append(line.rstrip("\r"))

    out: list[str] = []
    for word in words:
        reversed_word = word[::-1]
        is_palindrome = word == reversed_word
        out.append(f"{reversed_word} {is_palindrome}")

    out.append("-".join(words))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
