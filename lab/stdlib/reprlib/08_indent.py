import reprlib


def main():
    values = [1, 2, 3, 4, 5, 6]
    print("indent 4")
    print(reprlib.Repr(indent=4).repr(values))
    print("indent --")
    print(reprlib.Repr(indent="--").repr(values))
    print("nested indent 2")
    print(reprlib.Repr(indent=2).repr({"a": 1, "b": [2, 3], "c": 4}))
    print("tuple indent")
    print(reprlib.Repr(indent=2).repr((1, 2)))
    print("empty indent")
    print(reprlib.Repr(indent=2).repr([]))
    print("level 2")
    r = reprlib.Repr(indent=4, maxlevel=2)
    print(r.repr([1, [2, 3], 4]))
    try:
        reprlib.Repr(indent=-2).repr(values)
    except ValueError as error:
        print("error", str(error))


main()
