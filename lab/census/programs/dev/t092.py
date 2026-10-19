import sys


VOWELS = set("aeiou")


def replace_vowels(word: str) -> tuple[str, int]:
    """Return the word with vowels replaced by '*' and the number of replacements."""
    chars: list[str] = []
    count = 0
    for ch in word:
        if ch in VOWELS:
            chars.append("*")
            count += 1
        else:
            chars.append(ch)
    return "".join(chars), count


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    words = data[1:1 + n]
    lines: list[str] = []
    for word in words:
        replaced, count = replace_vowels(word)
        lines.append(f"{replaced} {count}")
    if lines:
        sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
