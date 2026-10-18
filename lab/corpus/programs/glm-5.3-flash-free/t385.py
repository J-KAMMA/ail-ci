import sys
from typing import List


def read_ints() -> List[int]:
    return [int(token) for token in sys.stdin.read().split()]


def main() -> None:
    data = read_ints()
    r, c = data[0], data[1]
    values = data[2:2 + r * c]
    rows: List[List[int]] = [values[i * c:(i + 1) * c] for i in range(r)]

    sorted_rows = sorted(rows, key=lambda row: (sum(row), row))
    for row in sorted_rows:
        print(" ".join(map(str, row)))

    columns: List[List[int]] = [[row[j] for row in sorted_rows] for j in range(c)]
    sorted_columns = sorted(columns, key=lambda col: (min(col), col))
    for col in sorted_columns:
        print(" ".join(map(str, col)))


if __name__ == "__main__":
    main()
