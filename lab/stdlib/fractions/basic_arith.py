from fractions import Fraction


def describe(label, x):
    print(label, str(x), repr(x), float(x), x.numerator, x.denominator)


def main():
    a = Fraction(3, 4)
    b = Fraction(5, 6)
    describe("a", a)
    describe("b", b)
    print(a + b, a - b, a * b, a / b)
    print(a + 1, 1 - a, a * 3, 2 * a, a / 2)
    print(a + 0.5, 0.25 + b, a * 2.0, b / 0.5)
    print(-a, +a, abs(Fraction(-7, 3)))
    print(bool(a), bool(Fraction(0)), int(Fraction(7, 2)), int(Fraction(-7, 2)))
    print(a == Fraction(6, 8), a != b, a < b, a <= b, a > b, a >= b)
    print(a == 0.75, a != 0.7, 1 > a, 0.5 < b)
    print(a.as_integer_ratio(), Fraction(4, 2).as_integer_ratio())
    print(a.is_integer(), Fraction(4, 2).is_integer())


main()
