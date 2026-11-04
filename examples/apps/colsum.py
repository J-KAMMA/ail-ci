"""Summarise one integer column of a CSV file with a header row."""

import csv
import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: colsum.py COLUMN", file=sys.stderr)
        sys.exit(2)
    column = sys.argv[1]
    rows = list(csv.reader(sys.stdin))
    if not rows:
        print("colsum: empty input, no header row", file=sys.stderr)
        sys.exit(2)
    header = rows[0]
    if column not in header:
        print("colsum: no such column: " + column, file=sys.stderr)
        sys.exit(2)
    index = header.index(column)
    count = 0
    total = 0
    low = 0
    high = 0
    first = True
    bad = 0
    for row in rows[1:]:
        if index >= len(row):
            bad += 1
            continue
        try:
            value = int(row[index])
        except ValueError:
            bad += 1
            continue
        count += 1
        total += value
        if first:
            low = value
            high = value
            first = False
        else:
            if value < low:
                low = value
            if value > high:
                high = value
    print("count %d" % count)
    if count == 0:
        print("sum 0")
        print("min -")
        print("max -")
        print("mean -")
    else:
        print("sum %d" % total)
        print("min %d" % low)
        print("max %d" % high)
        print("mean %.6f" % (total / count))
    print("nonint %d" % bad)


main()
