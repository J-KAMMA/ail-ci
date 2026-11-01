from array import array


def main():
    a = array('i', [1, 2, 3])
    b = array('i', [1, 3, 0])
    print(a == b, a != b, a < b, a <= b, a > b, a >= b)
    print(a == array('d', [1.0, 2.0, 3.0]))
    print(a == [1, 2, 3])
    c = a[:]
    c[0] = 99
    print(a, c)
    d = a + array('i', [4])
    print(d, a)
    a += array('i', [5])
    print(a, len(a))
    a *= 2
    print(a)
    try:
        print(a < [1, 2])
    except TypeError:
        print("TypeError")
    try:
        print(a + [1])
    except TypeError:
        print("TypeError")
    try:
        print(a * 2.0)
    except TypeError:
        print("TypeError")
    print(max(a), min(a), sorted(a.tolist())[:3])


main()
