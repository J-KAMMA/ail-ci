# task: Count the number of words on each line of a fixed multi-line string and print a histogram made of asterisks.
from typing import List


TEXT: str = """The quick brown fox jumps over the lazy dog.
Pack my box with five dozen liquor jugs.
How vexingly quick daft zebras jump!

Sphinx of black quartz, judge my vow.
Yes."""


def count_words_per_line(text: str) -> List[int]:
    """Return the number of whitespace-separated words on each line."""
    return [len(line.split()) for line in text.splitlines()]


def build_histogram(counts: List[int], symbol: str = "*") -> List[str]:
    """Build one histogram row per line, using the symbol repeated count times."""
    rows: List[str] = []
    for index, count in enumerate(counts, start=1):
        rows.append(f"Line {index:>2} | {symbol * count} ({count})")
    return rows


def main() -> None:
    counts: List[int] = count_words_per_line(TEXT)
    for row in build_histogram(counts):
        print(row)


if __name__ == "__main__":
    main()
