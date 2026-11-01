from array import array


def main():
    rows = []
    for text in ("3 1 2", "9 7 8", "4 5 6"):
        row = array('i')
        row.fromlist([int(x) for x in text.split()])
        rows.append(row)
    for row in rows:
        print(row, sum(row))
    joined = rows[0] + rows[1]
    print(joined, joined[2:5])
    print(rows[1] == array('i', [9, 7, 8]))
    print(sorted(rows[-1].tolist()))
    rows[2].reverse()
    print(rows[2])
    total = array('i')
    for row in rows:
        total.extend(row)
    print(total.tolist())


main()
