"""N-queens: count every placement of n non-attacking queens on an n-by-n board.

The search fills one row at a time; three boolean arrays reject a column, a
diagonal and an anti-diagonal.  It prints the number of solutions.
"""
import sys


def solve(n, row, cols, diag, anti):
    if row == n:
        return 1
    total = 0
    i = 0
    while i < n:
        if not cols[i] and not diag[row + i] and not anti[row - i + n]:
            cols[i] = True
            diag[row + i] = True
            anti[row - i + n] = True
            total += solve(n, row + 1, cols, diag, anti)
            cols[i] = False
            diag[row + i] = False
            anti[row - i + n] = False
        i += 1
    return total


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 13
    print(solve(n, 0, [False] * n, [False] * (2 * n), [False] * (2 * n)))


main()
