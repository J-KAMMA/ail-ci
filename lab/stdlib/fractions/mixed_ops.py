from fractions import Fraction
import math


def main():
    vals = [Fraction(-7, 3), Fraction(7, 3), Fraction(3, 1), Fraction(1, 2)]
    for i in range(len(vals)):
        a = vals[i]
        b = vals[(i + 1) % len(vals)]
        print("pair", a, b)
        print(a + b, a - b, a * b, a / b)
        print(a // b, a % b, divmod(a, b))
        print(b // a, b % a, divmod(b, a))
        print(a ** 2, a ** 3, a ** -2, a ** Fraction(2))
        print(2 ** a, a ** Fraction(1, 2).numerator if a == 0 else a)
        print(a < b, a <= b, a > b, a >= b, a == b, a != b)
        print(a < 2, a > -3.5, a == 0.5, a != 0.5)
        print(math.floor(a), math.ceil(a), math.trunc(a), int(a), float(a))
        print(abs(a), -a, +a, bool(a))


main()
