import numbers
from fractions import Fraction


def kind(value: numbers.Number) -> str:
    if isinstance(value, numbers.Integral):
        return "integral"
    if isinstance(value, numbers.Rational):
        return "rational"
    if isinstance(value, numbers.Real):
        return "real"
    if isinstance(value, numbers.Number):
        return "number"
    return "other"


def main():
    a = 7
    b = 2
    f = Fraction(3, 4)
    print("add", kind(a + b), kind(a / b), kind(a * b))
    print("float", kind(a + 0.5), kind(0.5 * b))
    print("fraction", kind(f + f), kind(f * 2), kind(f / 2))
    print("mixed", kind(f + a), kind(f * 2.0))
    print("bool", kind(True + True), kind(True * 3))
    print("power", kind(a ** b), kind(a ** -1))
    print("sum", kind(sum([1, 2, 3])), kind(sum([1, 2.5])))
    print("abs", kind(abs(-3)), kind(abs(f)))
    print("all", [kind(v) for v in [a, b, f, 1.5, True]])


main()
