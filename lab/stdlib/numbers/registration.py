import numbers


class Money:
    def __init__(self, cents):
        self.cents = cents


class Token:
    def __init__(self, value):
        self.value = value


class Plain:
    pass


@numbers.Number.register
class Measurement:
    def __init__(self, value):
        self.value = value


def main():
    registered = numbers.Number.register(Money)
    print(registered is Money)
    numbers.Integral.register(Token)
    print(isinstance(Money(100), numbers.Number), isinstance(Money(100), numbers.Integral))
    print(isinstance(Token(3), numbers.Integral), isinstance(Token(3), numbers.Real))
    print(isinstance(Measurement(1), numbers.Number), isinstance(Plain(), numbers.Number))
    print(issubclass(Money, numbers.Number), issubclass(Token, numbers.Integral))
    print(issubclass(Measurement, numbers.Complex), issubclass(Measurement, numbers.Integral))
    values = [Money(5), Token(6), Measurement(7), 8]
    print([isinstance(v, numbers.Number) for v in values])
    print([isinstance(v, numbers.Integral) for v in values])


main()
