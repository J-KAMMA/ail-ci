import numbers


class Meters(numbers.Number):
    def __init__(self, value):
        self.value = value


class Ratio(numbers.Rational):
    pass


class Address:
    pass


def main():
    print("int", issubclass(int, numbers.Integral), issubclass(int, numbers.Real))
    print("bool", issubclass(bool, numbers.Integral), issubclass(bool, numbers.Number))
    print("float", issubclass(float, numbers.Real), issubclass(float, numbers.Complex))
    print("str", issubclass(str, numbers.Number), issubclass(list, numbers.Number))
    print("classes", issubclass(Meters, numbers.Number), issubclass(Meters, numbers.Integral))
    print("ratio", issubclass(Ratio, numbers.Rational), issubclass(Ratio, numbers.Real))
    print("address", issubclass(Address, numbers.Number))
    distance = Meters(3)
    print("instance", isinstance(distance, numbers.Number))
    print("type", issubclass(type(distance), numbers.Number), issubclass(type("x"), numbers.Number))
    print("tuple", issubclass(int, (numbers.Real, numbers.Integral)))


main()
