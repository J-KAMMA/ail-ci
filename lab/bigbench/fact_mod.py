"""4000! as one exact integer.

The factorial has 12674 decimal digits.  We print it modulo 10^9+7, its bit
length, and the sum of its base-10^9 limbs (repeated divmod on a copy), so no
printed value approaches the 4300-digit str() limit.  math.factorial is used
so the value is created by the big-int capable function (a hand-rolled product
loop is folded into int64 by the typed path's local proof).
"""
import math


def main() -> None:
    f = math.factorial(4000)
    print(f % (10 ** 9 + 7))
    print(f.bit_length())
    total = 0
    x = f
    while x > 0:
        x, r = divmod(x, 10 ** 9)
        total = total + r
    print(total)


main()
