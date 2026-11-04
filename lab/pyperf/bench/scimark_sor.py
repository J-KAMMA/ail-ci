"""SciMark SOR: red-black successive over-relaxation on a square grid.

The interior starts at one, the omega factor is 1.25, and each sweep updates
one colour then the other until every cell has converged; the total change of
the last sweep is printed.
"""
import sys
import math


def sor(n, reps):
    omega = 1.25
    grid = []
    i = 0
    while i < n:
        row = [0.0] * n
        row[0] = 1.0
        row[n - 1] = 1.0
        grid.append(row)
        i += 1
    grid[0] = [1.0] * n
    grid[n - 1] = [1.0] * n
    change = 0.0
    rep = 0
    while rep < reps:
        i = 1
        while i < n - 1:
            gi = grid[i]
            up = grid[i - 1]
            down = grid[i + 1]
            j = 1 + (i & 1)
            while j < n - 1:
                value = omega * ((gi[j - 1] + gi[j + 1] + up[j] + down[j]) * 0.25 - gi[j]) + gi[j]
                gi[j] = value
                j += 2
            i += 1
        i = 1
        while i < n - 1:
            gi = grid[i]
            up = grid[i - 1]
            down = grid[i + 1]
            j = 2 - (i & 1)
            while j < n - 1:
                value = omega * ((gi[j - 1] + gi[j + 1] + up[j] + down[j]) * 0.25 - gi[j]) + gi[j]
                gi[j] = value
                j += 2
            i += 1
        rep += 1
    change = 0.0
    i = 1
    while i < n - 1:
        gi = grid[i]
        j = 1
        while j < n - 1:
            change += (gi[j] - 1.0) * (gi[j] - 1.0)
            j += 1
        i += 1
    return math.sqrt(change)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    reps = 400
    print("%.9f" % sor(n, reps))


main()
