import numbers
from decimal import Decimal
from fractions import Fraction


def kind(value):
    if isinstance(value, numbers.Integral):
        return "integral"
    if isinstance(value, numbers.Rational):
        return "rational"
    if isinstance(value, numbers.Real):
        return "real"
    if isinstance(value, numbers.Complex):
        return "complex"
    if isinstance(value, numbers.Number):
        return "number"
    return "other"


def main():
    values = [7, True, 2.5, Fraction(3, 4), Decimal("1.25"), "7", None, [1, 2]]
    for value in values:
        print(repr(value), kind(value))
    for value in []:
        print("unreachable", kind(value))
    print("counts", [kind(v) for v in values])
    half = Fraction(1, 2)
    print("mixed", isinstance(half, (numbers.Real, str)))
    print("none", isinstance(None, numbers.Number))


main()
