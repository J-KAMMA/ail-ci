import reprlib


def main():
    values = list(range(20))
    print(reprlib.repr(values))
    print(reprlib.repr(values[:5]))
    nested = [list(range(10)), list(range(10, 20)), [1, 2, 3]]
    print(reprlib.repr(nested))
    print(reprlib.repr(()))
    print(reprlib.repr((1,)))
    print(reprlib.repr(tuple(range(10))))
    print(reprlib.repr([]))


main()
