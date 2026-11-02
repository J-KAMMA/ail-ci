from array import array


def main():
    a = array('i')
    print(a, len(a), a.tolist())
    try:
        a.pop()
    except IndexError as exc:
        print("IndexError", exc)
    a.extend([1, 2, 3])
    try:
        a.index(9)
    except ValueError as exc:
        print("ValueError", exc)
    try:
        a.remove(9)
    except ValueError as exc:
        print("ValueError", exc)
    try:
        print(a[10])
    except IndexError as exc:
        print("IndexError", exc)
    try:
        a[0] = 1.5
    except TypeError as exc:
        print("TypeError", exc)
    try:
        a[1:2] = [7]
    except TypeError as exc:
        print("TypeError", exc)
    try:
        a[1:2] = array('d', [7.0])
    except TypeError as exc:
        print("TypeError", exc)
    a[1:2] = array('i', [7, 8, 9])
    print(a.tolist())
    del a[::-1]
    print(a)
    try:
        array('i', [1])[5] = 0
    except IndexError as exc:
        print("IndexError", exc)


main()
