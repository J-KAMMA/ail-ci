import numbers


class Euro:
    def __init__(self, amount):
        self.amount = amount


class Share:
    def __init__(self, count):
        self.count = count


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y


numbers.Number.register(Euro)
numbers.Rational.register(Share)
numbers.Complex.register(Point)


def flags(value):
    return (isinstance(value, numbers.Integral),
            isinstance(value, numbers.Rational),
            isinstance(value, numbers.Real),
            isinstance(value, numbers.Complex),
            isinstance(value, numbers.Number))


def main():
    for value in [Euro(10), Share(3), Point(1, 2), 5, 2.0, "x"]:
        print(type(value).__name__, flags(value))
    print(issubclass(Share, numbers.Rational), issubclass(Share, numbers.Real))
    print(issubclass(Point, numbers.Complex), issubclass(Point, numbers.Real))
    print(issubclass(Euro, numbers.Number), issubclass(Euro, numbers.Complex))


main()
