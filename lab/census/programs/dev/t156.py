import sys


def main() -> None:
    rows: list[tuple[str, int]] = []
    for line in sys.stdin:
        parts = line.split()
        if len(parts) != 2:
            continue
        word, number = parts
        rows.append((word, int(number)))

    # Lines sorted by number descending, then word ascending.
    for word, number in sorted(rows, key=lambda r: (-r[1], r[0])):
        print(f"{word} {number}")

    # Total per word via a dict comprehension, printed sorted by key.
    totals: dict[str, int] = {
        w: sum(n for ww, n in rows if ww == w) for w in {w for w, _ in rows}
    }
    for word in sorted(totals):
        print(f"{word} {totals[word]}")


if __name__ == "__main__":
    main()
