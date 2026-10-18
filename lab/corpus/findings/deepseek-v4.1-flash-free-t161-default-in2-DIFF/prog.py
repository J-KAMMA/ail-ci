import sys
from dataclasses import dataclass


@dataclass
class Row:
    a: int
    b: int
    word: str


def main() -> None:
    rows: list[Row] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        a, b, word = line.split(",")
        rows.append(Row(a=int(a), b=int(b), word=word))

    rows.sort(key=lambda row: (row.word, row.a))

    for row in rows:
        print(repr(row))


if __name__ == "__main__":
    main()
