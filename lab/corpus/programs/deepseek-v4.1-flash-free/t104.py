import sys


def main() -> None:
    words = sys.stdin.read().split()
    first_index: dict[str, int] = {}
    lines: list[str] = []

    for i, word in enumerate(words):
        key = "".join(sorted(word))
        if key in first_index:
            lines.append(f"{word} {first_index[key]}")
        else:
            first_index[key] = i

    if lines:
        sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
