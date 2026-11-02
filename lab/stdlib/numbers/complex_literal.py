import numbers


def main():
    z = 1 + 2j
    print(z, z.real, z.imag)
    print(isinstance(z, numbers.Complex))
    print(isinstance(z, numbers.Number))
    print(isinstance(z, numbers.Real))
    print(z * 2, abs(z))
    print(issubclass(type(z), numbers.Complex))
    values = [z, 3, 2.5, "z"]
    print([isinstance(v, numbers.Complex) for v in values])
    print([isinstance(v, (numbers.Real, numbers.Complex)) for v in values])


main()
