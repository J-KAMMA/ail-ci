import sys
from itertools import groupby
from typing import Iterable


def first_letter(word: str) -> str:
    return word[0]


def format_groups(words: Iterable[str]) -> str:
    lines: list[str] = []
    for letter, group in groupby(sorted(words), key=first_letter):
        items = list(group)
        lines.append(f"{letter} {len(items)} {'/'.join(items)}")
    return "\n".join(lines)


def main() -> None:
    words = sys.stdin.read().split()
    output = format_groups(words)
    if output:
        print(output)


if __name__ == "__main__":
    main()
