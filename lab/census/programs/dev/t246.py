import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    r = int(data[0])
    c = int(data[1])
    values = list(map(int, data[2:]))

    rows: list[list[int]] = []
    for i in range(r):
        start = i * c
        rows.append(values[start:start + c])

    # Rows sorted lexicographically as lists.
    for row in sorted(rows):
        print(row)

    # Row with the largest sum; max() returns the first maximal element on ties.
    if rows:
        best = max(rows, key=sum)
        print(best)
    else:
        print([])

    # Number of zero entries.
    zero_count = sum(1 for x in values[:r * c] if x == 0)
    print(zero_count)


if __name__ == "__main__":
    main()
