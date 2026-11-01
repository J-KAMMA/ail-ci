import numbers
from fractions import Fraction


def mean(values):
    if not values:
        raise ValueError("mean() of an empty sequence")
    total = 0
    for value in values:
        if not isinstance(value, numbers.Real):
            raise TypeError("not a real number: %r" % (value,))
        total = total + value
    return total / len(values)


def main():
    for data in ([1, 2, 3, 4], [1.5, 2.5], [True, False, True], [Fraction(1, 3)] * 3):
        print(data, mean(data))
    for data in ([], [1, "2", 3], [1, None]):
        try:
            print("mean", mean(data))
        except (TypeError, ValueError) as exc:
            print(type(exc).__name__, exc)
    print("empty check", isinstance([], numbers.Number))


main()
