import numbers


class Celsius(numbers.Number):
    def __init__(self, degrees):
        self.degrees = degrees

    def __repr__(self):
        return "Celsius(%s)" % self.degrees

    def __eq__(self, other):
        if isinstance(other, Celsius):
            return self.degrees == other.degrees
        return self.degrees == other

    def __add__(self, other):
        if isinstance(other, Celsius):
            return Celsius(self.degrees + other.degrees)
        return Celsius(self.degrees + other)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, Celsius):
            return Celsius(self.degrees - other.degrees)
        return Celsius(self.degrees - other)

    def __mul__(self, other):
        return Celsius(self.degrees * other)

    def __truediv__(self, other):
        return Celsius(self.degrees / other)

    def __lt__(self, other):
        return self.degrees < other


def main():
    a = Celsius(20)
    b = Celsius(5)
    print(a, b, a + b, a + 1, 1 + a, a - b, a * 2, a / 4)
    print(a == Celsius(20), a == 20, a < 25, isinstance(a, numbers.Number))
    print(isinstance(a, numbers.Complex), isinstance(a, numbers.Real))
    print(issubclass(Celsius, numbers.Number), issubclass(Celsius, numbers.Integral))
    print([c.degrees for c in [a, b, a + b]])


main()
