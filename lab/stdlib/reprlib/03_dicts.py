import reprlib


def main():
    squares = {}
    for i in range(10):
        squares[i] = i * i
    print("squares", reprlib.repr(squares))
    nested = {"a": [1, 2, 3, 4, 5, 6, 7], "b": {"x": 1, "y": 2}, "c": "text"}
    print("nested", reprlib.repr(nested))
    mixed = {}
    mixed[1] = "int"
    mixed["two"] = 2
    mixed[(3, 4)] = "tuple"
    mixed[None] = "none"
    print("mixed", reprlib.repr(mixed))
    print("empty", reprlib.repr({}))
    exactly = {1: "a", 2: "b", 3: "c", 4: "d"}
    print("exactly", reprlib.repr(exactly))
    one_more = {1: "a", 2: "b", 3: "c", 4: "d", 5: "e"}
    print("one more", reprlib.repr(one_more))


main()
