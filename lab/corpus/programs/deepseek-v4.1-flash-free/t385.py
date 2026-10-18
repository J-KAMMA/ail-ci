import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    pos = 0
    r = int(data[pos]); pos += 1
    c = int(data[pos]); pos += 1

    rows: list[list[int]] = []
    for _ in range(r):
        rows.append([int(data[pos + j]) for j in range(c)])
        pos += c

    rows.sort(key=lambda row: (sum(row), row))

    lines = [" ".join(map(str, row)) for row in rows]
    sys.stdout.write("\n".join(lines) + ("\n" if lines else ""))

    cols: list[list[int]] = [list(col) for col in zip(*rows)]
    cols.sort(key=lambda col: (min(col), col))
    sorted_rows = [list(row) for row in zip(*cols)] if cols else []

    lines = [" ".join(map(str, row)) for row in sorted_rows]
    sys.stdout.write("\n".join(lines) + ("\n" if lines else ""))


if __name__ == "__main__":
    main()
