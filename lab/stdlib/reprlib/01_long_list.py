import reprlib


def main():
    numbers = list(range(30))
    print("numbers", reprlib.repr(numbers))
    words = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta",
             "theta", "iota", "kappa"]
    print("words", reprlib.repr(words))
    short = [1, 2, 3]
    print("short", reprlib.repr(short))
    exactly = [10, 20, 30, 40, 50, 60]
    print("exactly", reprlib.repr(exactly))
    one_more = [10, 20, 30, 40, 50, 60, 70]
    print("one more", reprlib.repr(one_more))
    empty = []
    print("empty", reprlib.repr(empty))
    mixed = [1, "two", 3.0, None, [4, 5, 6, 7, 8, 9, 10]]
    print("mixed", reprlib.repr(mixed))


main()
