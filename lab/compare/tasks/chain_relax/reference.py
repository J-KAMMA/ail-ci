"""Reference implementation of chain_relax (see spec.md): reference.py N T SEED

Python floats are IEEE binary64 and every operation below is a single rounded operation, in the
order the spec gives. Exits with status 99 if a printed value is an exact rounding tie (the test
generator must not produce those).
"""
import re
import sys
from fractions import Fraction
from math import sqrt

M64 = (1 << 64) - 1


def fmt(v):
    x = Fraction(v) * 10 ** 9
    if x - (x.numerator // x.denominator) == Fraction(1, 2):
        sys.stderr.write('exact tie: %r\n' % v)
        sys.exit(99)
    s = '%.9f' % v
    if s == '-0.000000000':
        s = '0.000000000'
    return s


def main(argv):
    if len(argv) != 4 or not all(re.fullmatch(r'[0-9]+', a) for a in argv[1:]):
        return 1
    n, t, seed = int(argv[1]), int(argv[2]), int(argv[3])
    if not (1 <= n <= 10000000 and t <= 1000000 and seed <= M64):
        return 1
    x = seed
    h = [0.0] * n
    for i in range(n):
        x = (x * 6364136223846793005 + 1442695040888963407) & M64
        h[i] = float(((x >> 33) % 2001) - 1000) / 64.0
    last = n - 1
    for s in range(1, t + 1):
        if s & 1:
            # i = 0 .. n-1; left neighbour of 0 is h[n-1], right neighbour of n-1 is h[0]
            l = h[last]
            for i in range(last):
                c = h[i]
                d = (l + h[i + 1]) - (c + c)
                l = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
                h[i] = l
            c = h[last]
            d = (l + h[0]) - (c + c)
            h[last] = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
        else:
            r = h[0]
            for i in range(last, 0, -1):
                c = h[i]
                d = (h[i - 1] + r) - (c + c)
                r = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
                h[i] = r
            c = h[0]
            d = (h[last] + r) - (c + c)
            h[0] = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
    total = 0.0
    energy = 0.0
    for i in range(n):
        total = total + h[i]
        dd = h[(i + 1) % n] - h[i]
        energy = energy + dd * dd
    out = ['sum ' + fmt(total), 'energy ' + fmt(energy), 'min ' + fmt(min(h)), 'max ' + fmt(max(h)),
           'first ' + fmt(h[0]), 'middle ' + fmt(h[n // 2]), 'last ' + fmt(h[last])]
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
