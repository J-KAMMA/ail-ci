"""Gibbons' unbounded spigot: 2000 decimal digits of pi, ten per line.

The spigot keeps q, r, t, k, n, l as exact integers.  They grow past int64
after a few dozen digits, so this program needs arbitrary-precision multiply,
divide and compare.  Each printed line is a ten-character string of digits.
"""


def main() -> None:
    digits: list[int] = []
    q = 1
    r = 0
    t = 1
    k = 1
    n = 3
    l = 3
    while len(digits) < 2000:
        if 4 * q + r - t < n * t:
            # emit the digit, then advance the three quotient/remainder terms
            digits.append(n)
            nq = 10 * q
            nr = 10 * (r - n * t)
            nn = (10 * (3 * q + r)) // t - 10 * n
            q = nq
            r = nr
            n = nn
        else:
            # refine the approximation; every right-hand side uses the old values
            nq = q * k
            nr = (2 * q + r) * l
            nt = t * l
            nk = k + 1
            nn = (q * (7 * k + 2) + r * l) // (t * l)
            nl = l + 2
            q = nq
            r = nr
            t = nt
            k = nk
            n = nn
            l = nl
    i = 0
    while i < len(digits):
        line = ""
        j = 0
        while j < 10 and i + j < len(digits):
            line = line + str(digits[i + j])
            j = j + 1
        print(line)
        i = i + 10


main()
