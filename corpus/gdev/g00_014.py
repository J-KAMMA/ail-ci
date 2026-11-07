# task: Write a script that finds the longest common prefix among a hardcoded list of strings and prints it.
from typing import Sequence


def longest_common_prefix(strings: Sequence[str]) -> str:
    """Return the longest common prefix shared by all strings."""
    if not strings:
        return ""
    shortest = min(strings, key=len)
    for i, ch in enumerate(shortest):
        for s in strings:
            if s[i] != ch:
                return shortest[:i]
    return shortest


def main() -> None:
    words: list[str] = [
        "flower",
        "flow",
        "flight",
        "flourish",
        "flock",
    ]
    prefix = longest_common_prefix(words)
    print(f"Longest common prefix: {prefix!r}")


if __name__ == "__main__":
    main()
