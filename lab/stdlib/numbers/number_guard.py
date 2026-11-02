import numbers
from decimal import Decimal
from fractions import Fraction


def require_real(value, name):
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        return float(value)
    raise TypeError("%s must be a real number, got %s" % (name, type(value).__name__))


def process(label, value):
    try:
        print(label, require_real(value, label))
    except TypeError as exc:
        print("TypeError", exc)


def main():
    for label, value in [("int", 4), ("bool", True), ("float", 2.5),
                         ("fraction", Fraction(3, 2)), ("decimal", Decimal("1.5")),
                         ("str", "4"), ("none", None)]:
        process(label, value)
    print("real", isinstance(Fraction(1, 1), numbers.Real))
    print("not integral", isinstance(2.0, numbers.Integral))


main()
