import sys

PUNCTUATION = ",.!;"


def clean(word: str) -> str:
    return word.rstrip(PUNCTUATION)


def main() -> None:
    lines = sys.stdin.read().splitlines()
    result: list[str] = []
    for line in lines:
        if line == "":
            result.append("0 0 -")
            continue
        longest = ""
        for word in line.split(" "):
            stripped = clean(word)
            if len(stripped) > len(longest):
                longest = stripped
        word_out = longest if longest else "-"
        result.append(f"{len(line)} {len(longest)} {word_out}")
    sys.stdout.write("\n".join(result) + ("\n" if result else ""))


if __name__ == "__main__":
    main()
