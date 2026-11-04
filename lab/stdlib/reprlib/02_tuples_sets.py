import reprlib


def main():
    print("tuple", reprlib.repr(tuple(range(10))))
    print("one", reprlib.repr((1,)))
    print("empty tuple", reprlib.repr(()))
    print("six", reprlib.repr((1, 2, 3, 4, 5, 6)))
    print("seven", reprlib.repr((1, 2, 3, 4, 5, 6, 7)))
    values = {3, 1, 2, 10, 9, 8, 7, 6, 5, 4}
    print("set", reprlib.repr(values))
    frozen = frozenset({1, 2, 3, 4, 5, 6, 7, 8})
    print("frozenset", reprlib.repr(frozen))
    print("empty set", reprlib.repr(set()))
    print("empty frozenset", reprlib.repr(frozenset()))
    print("nested", reprlib.repr([(1, 2), {3, 4}, frozenset({5, 6})]))


main()
