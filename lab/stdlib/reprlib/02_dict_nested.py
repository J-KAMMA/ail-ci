import reprlib


def main():
    data = {"alpha": 1, "beta": 2, "gamma": 3, "delta": 4, "epsilon": 5}
    print(reprlib.repr(data))
    print(reprlib.repr({"only": 1}))
    print(reprlib.repr({}))
    matrix = [[1, 2], [3, 4], [5, 6]]
    print(reprlib.repr(matrix))
    deep = [[[["x"]]]]
    print(reprlib.repr(deep))
    print(reprlib.repr({"outer": {"inner": [1, 2, 3, 4, 5, 6, 7]}}))


main()
