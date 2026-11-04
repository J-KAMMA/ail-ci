"""Spectral norm: power iteration on A where A(i,j) = 1/((i+j)*(i+j+1)/2 + i + 1).

Ten rounds of v <- A^T A v, normalising each time, give the largest singular
value of the infinite matrix.  The result is printed with nine decimals.
"""
import sys
import math


def eval_a(i, j):
    return 1.0 / ((i + j) * (i + j + 1) // 2 + i + 1)


def eval_atv(v, out, n):
    i = 0
    while i < n:
        total = 0.0
        j = 0
        while j < n:
            total += eval_a(j, i) * v[j]
            j += 1
        out[i] = total
        i += 1


def eval_ata(v, out, tmp, n):
    eval_atv(v, tmp, n)
    eval_atv(tmp, out, n)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 700
    u = [1.0] * n
    v = [0.0] * n
    tmp = [0.0] * n
    i = 0
    while i < 10:
        eval_ata(u, v, tmp, n)
        eval_ata(v, u, tmp, n)
        i += 1
    vbv = 0.0
    vv = 0.0
    i = 0
    while i < n:
        vbv += u[i] * v[i]
        vv += v[i] * v[i]
        i += 1
    print("%.9f" % math.sqrt(vbv / vv))


main()
