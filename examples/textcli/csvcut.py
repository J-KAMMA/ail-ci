"""csvcut.py NAME[,NAME...]: cut named columns out of a CSV read from stdin."""
import csv
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("csvcut: usage: csvcut.py NAME[,NAME...]", file=sys.stderr)
        return 2
    names = sys.argv[1].split(",")
    text = sys.stdin.read()
    lines = text.splitlines()
    rows = list(csv.reader(lines))
    if len(rows) == 0:
        return 0
    header = rows[0]
    missing = ""
    for name in names:
        if name not in header:
            missing = name
    if len(missing) > 0:
        print("csvcut: no such column: " + missing, file=sys.stderr)
        return 2
    writer = csv.writer(sys.stdout, lineterminator="\n")
    for row in rows:
        picked = []
        for name in names:
            picked.append(row[header.index(name)])
        writer.writerow(picked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
