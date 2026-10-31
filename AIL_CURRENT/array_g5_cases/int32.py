import ail_array as ta


def digest(r: ta.Array[ta.int32]) -> str:
    n = len(r)
    if n <= 4100:
        data = r.tobytes()
        h = 0
        for i in range(len(data)):
            h = (h * 31 + data[i]) % 1000000007
        return str(n) + ":" + str(h)
    return str(n) + ":" + str(ta.sum(r)) + ":" + str(r[0]) + ":" + str(r[n // 2]) + ":" + str(r[n - 1]) + ":" + str(ta.min(r)) + ":" + str(ta.max(r))


def make(kind: int, n: int) -> ta.Array[ta.int32]:
    a = ta.zeros(n, ta.int32)
    seed = 4242 + (kind % 16) * 15485863
    for k in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        if kind == 0:
            a[k] = seed % 2001 - 1000
        elif kind == 1:
            a[k] = seed % 40001 - 20000
        elif kind == 2:
            a[k] = 2147483647 - (seed % 5)
        elif kind == 3:
            a[k] = -2147483648 + (seed % 5)
        else:
            a[k] = (seed % 65537) - 32768
    return a


def ops(label: str, a: ta.Array[ta.int32], b: ta.Array[ta.int32]):
    try:
        print(label, "add", digest(a + b))
    except OverflowError as e:
        print(label, "add", "OverflowError", e)
    try:
        print(label, "sub", digest(a - b))
    except OverflowError as e:
        print(label, "sub", "OverflowError", e)
    try:
        print(label, "mul", digest(a * b))
    except OverflowError as e:
        print(label, "mul", "OverflowError", e)
    try:
        print(label, "adds", digest(a + 5), digest(7 + a))
    except OverflowError as e:
        print(label, "adds", "OverflowError", e)
    try:
        print(label, "subs", digest(a - 3), digest(3 - a))
    except OverflowError as e:
        print(label, "subs", "OverflowError", e)
    try:
        print(label, "muls", digest(a * 3), digest(65536 * a))
    except OverflowError as e:
        print(label, "muls", "OverflowError", e)
    try:
        print(label, "range", digest(a + 4294967296))
    except OverflowError as e:
        print(label, "range", "OverflowError", e)


def main():
    lengths = [0, 1, 2, 63, 64, 65, 127, 128, 129, 4095, 4096, 4097, 100003]
    for n in lengths:
        for kind in range(2):
            ops("n%d_k%d" % (n, kind), make(kind, n), make((kind + 1) % 2, n))
    # overflow at chosen positions: the OverflowError names the operation and the lowest failing index
    for n in [65, 4097]:
        for pos in [0, 1, 63, 64, n - 1]:
            for kind in range(2, 5):
                a = make(kind, n)
                b = make(0, n)
                a[pos] = 2147483647
                b[pos] = 1
                a[(pos + 5) % n] = -2147483648
                ops("ov%d_%d_%d" % (n, pos, kind), a, b)
    # shapes
    p = ta.zeros(5, ta.int32)
    q = ta.zeros(6, ta.int32)
    try:
        print(digest(p + q))
    except ValueError as e:
        print("ValueError", e)
    # chains are separate passes: the OverflowError of the multiplication comes first
    a = make(0, 4000)
    b = make(0, 4000)
    a[3000] = 2147483647
    b[3000] = 2
    a[10] = 2147483647
    try:
        print(digest(a + b * b))
    except OverflowError as e:
        print("OverflowError", e)
    try:
        print(digest(a * b + a))
    except OverflowError as e:
        print("OverflowError", e)


main()
