from fractions import Fraction


def main():
    a = Fraction(numerator=3, denominator=4)
    b = Fraction(3, denominator=4)
    print(a, b, Fraction(numerator=7), Fraction(denominator=8))
    x = Fraction.from_float(0.1)
    y = Fraction.from_float(-2.5)
    print(x, y, x.as_integer_ratio(), y.as_integer_ratio())
    for f in [Fraction(1, 3), Fraction(22, 7), Fraction(355, 113), Fraction(-1, 3)]:
        print(f, round(f), round(f, 2), round(f, ndigits=-1), round(f, ndigits=0))
    for d in [1, 2, 10, 100, 1000000]:
        f = Fraction(355, 113)
        print(d, f.limit_denominator(d), f.limit_denominator(max_denominator=d))
    try:
        Fraction(1, 2).limit_denominator(0)
    except ValueError as exc:
        print(type(exc).__name__, str(exc))


main()
