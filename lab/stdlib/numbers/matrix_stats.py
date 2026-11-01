import numbers


def row_sum(row):
    total = 0
    for value in row:
        if not isinstance(value, numbers.Real):
            raise TypeError("bad cell %r" % (value,))
        total = total + value
    return total


def main():
    matrix = [[1, 2, 3], [4.5, 5.5], [True, False]]
    totals = []
    for row in matrix:
        totals.append(row_sum(row))
    print("totals", totals)
    print("grand", sum(totals))
    for row in ([], [1, "x"], [None], [1, 2.5]):
        try:
            print("row", row, row_sum(row))
        except TypeError as exc:
            print("TypeError", exc)
    empty = []
    print("empty", len(empty), sum(empty))
    print("real", all(isinstance(cell, numbers.Real) for row in matrix for cell in row))


main()
