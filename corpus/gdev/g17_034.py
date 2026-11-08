# task: Group case-insensitively equal words by sorting with key=str.lower and then collecting runs with itertools.groupby.
from itertools import groupby
from typing import Iterable


def group_case_insensitive(words: Iterable[str]) -> list[tuple[str, list[str]]]:
    """Group words that are equal ignoring case.

    Words are sorted by their lowercased form (a stable sort, so the original
    order is preserved within each group), then consecutive runs with the same
    lowercased key are collected with itertools.groupby.
    """
    ordered = sorted(words, key=str.lower)
    groups: list[tuple[str, list[str]]] = []
    for key, run in groupby(ordered, key=str.lower):
        groups.append((key, list(run)))
    return groups


def main() -> None:
    words: list[str] = [
        "Apple",
        "banana",
        "apple",
        "Cherry",
        "BANANA",
        "cherry",
        "date",
        "Date",
        "elderberry",
        "fig",
        "FIG",
        "apple",
        "Zebra",
        "zebra",
        "Mango",
    ]

    for key, members in group_case_insensitive(words):
        print(f"{key}: {', '.join(members)}")


if __name__ == "__main__":
    main()
