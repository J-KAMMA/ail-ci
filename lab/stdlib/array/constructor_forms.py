from array import array as arr


def main():
    print(arr('i'))
    print(arr('i', ()))
    print(arr('i', [3, 1, 2]))
    print(arr('h', range(-2, 3)))
    print(arr('B', b'ABC'))
    print(arr('b', bytearray([1, 2, 3])))
    print(arr('d', (x / 2 for x in range(5))))
    data = arr('l', [2 ** 40, -(2 ** 40)])
    print(data, data.itemsize, data.typecode)
    empty = arr('I')
    empty.extend([0, 1, 4294967295])
    print(empty, len(empty))
    try:
        arr('b', [128])
    except OverflowError as exc:
        print("OverflowError", exc)
    try:
        arr('h', [1.0])
    except TypeError as exc:
        print("TypeError", exc)
    try:
        arr('x')
    except ValueError as exc:
        print("ValueError", exc)


main()
