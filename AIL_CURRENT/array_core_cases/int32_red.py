import ail_array as ta


def fill(n: int, seed0: int) -> ta.Array[ta.int32]:
    a = ta.zeros(n, ta.int32)
    seed = seed0
    for k in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        a[k] = seed % 2097153 - 1048576
    return a


def ext(cell: str, a: ta.Array[ta.int32]):
    print("min int32|", cell, ta.min(a))
    print("max int32|", cell, ta.max(a))
    print("argmin int32|", cell, ta.argmin(a))
    print("argmax int32|", cell, ta.argmax(a))


def main():
    for n in [0, 1, 15, 16, 17, 1023, 1024, 1025, 5000]:
        a = fill(n, n + 1)
        b = fill(n, n + 5)
        print("sum int32|", n, ta.sum(a))
        print("dot int32|", n, ta.dot(a, b))
    h = ta.full(2, 2147483647, ta.int32)
    m = ta.full(1, -2147483648, ta.int32)
    print("sum int32|", ta.sum(ta.full(5000, 2147483647, ta.int32)), ta.sum(ta.full(5000, -2147483648, ta.int32)))
    print("sum int32|", ta.sum(h), ta.sum(m))
    print("dot int32|", ta.dot(h, h), ta.dot(m, m), ta.dot(h[0:1], m))
    ext("ties", ta.array([3, 1, 1, 5, 5, -2, -2], ta.int32))
    ext("limits", ta.array([0, 2147483647, -2147483648, 2147483647, -2147483648], ta.int32))
    ext("one", ta.array([7], ta.int32))
    ext("big", fill(5000, 3))
    e = ta.zeros(0, ta.int32)
    try:
        print(ta.max(e))
    except ValueError as x:
        print("max int32|", "ValueError", x)
    try:
        print(ta.argmin(e))
    except ValueError as x:
        print("argmin int32|", "ValueError", x)
    try:
        print(ta.dot(ta.zeros(2, ta.int32), ta.zeros(1, ta.int32)))
    except ValueError as x:
        print("dot int32|", "ValueError", x)


main()
