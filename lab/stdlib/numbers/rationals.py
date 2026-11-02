import numbers
from decimal import Decimal
from fractions import Fraction


def describe(value):
    return (isinstance(value, numbers.Integral),
            isinstance(value, numbers.Rational),
            isinstance(value, numbers.Real),
            isinstance(value, numbers.Number))


def main():
    items = [Fraction(1, 2), Fraction(6, 4), Decimal("0.5"), 1, 2.0]
    for item in items:
        print(item, describe(item))
    print("sum", sum([Fraction(1, 3), Fraction(1, 6)]))
    print("result", describe(Fraction(1, 2) + Fraction(1, 3)))
    print("divide", describe(Fraction(1, 2) / 2))
    print("empty", sum([]), describe(sum([])))
    try:
        print(Fraction(1, 0))
    except ZeroDivisionError as exc:
        print("ZeroDivisionError", exc)
    print("decimal only", isinstance(Decimal("2"), numbers.Real))
    print("fraction only", isinstance(Fraction(2, 1), numbers.Integral))


main()
