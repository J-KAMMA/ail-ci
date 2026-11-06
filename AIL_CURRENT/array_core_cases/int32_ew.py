import ail_array as ta


def show(cell: str, a: ta.Array[ta.int32]):
    print(cell + "|", a, a.tobytes().hex())


def rot(a: ta.Array[ta.int32], s: int) -> ta.Array[ta.int32]:
    n = len(a)
    b = ta.zeros(n, ta.int32)
    for k in range(n):
        b[k] = a[(k + s) % n]
    return b


def binop(op: int, a: ta.Array[ta.int32], b: ta.Array[ta.int32]):
    names = ["add", "sub", "mul", "floordiv", "mod"]
    cell = names[op] + " int32"
    try:
        if op == 0:
            show(cell, a + b)
        elif op == 1:
            show(cell, a - b)
        elif op == 2:
            show(cell, a * b)
        elif op == 3:
            show(cell, a // b)
        else:
            show(cell, a % b)
    except OverflowError as e:
        print(cell + "|", "OverflowError", e)
    except ZeroDivisionError as e:
        print(cell + "|", "ZeroDivisionError", e)


def scal(op: int, a: ta.Array[ta.int32], x: int):
    names = ["add", "sub", "mul", "floordiv", "mod"]
    cell = names[op] + " int32"
    try:
        if op == 0:
            show(cell, a + x)
        elif op == 1:
            show(cell, x - a)
        elif op == 2:
            show(cell, a * x)
        elif op == 3:
            show(cell, a // x)
        else:
            show(cell, x % a)
    except OverflowError as e:
        print(cell + "|", "OverflowError", e)
    except ZeroDivisionError as e:
        print(cell + "|", "ZeroDivisionError", e)


def unary(neg: bool, a: ta.Array[ta.int32]):
    cell = ("neg" if neg else "abs") + " int32"
    try:
        if neg:
            show(cell, -a)
        else:
            show(cell, abs(a))
    except OverflowError as e:
        print(cell + "|", "OverflowError", e)


def main():
    big = 2147483647
    small = -2147483648
    safe = ta.array([0, 1, -1, 7, -7, 3, -3, 46340, -46341, 65536, 1000000, -999999, 2, 5], ta.int32)
    nz = ta.array([1, -1, 2, -2, 3, -3, 5, 7, -7, 9, 11, -13, 17, 19], ta.int32)
    for op in range(5):
        binop(op, safe, nz)
        binop(op, nz, rot(nz, 3))
    for x in [1, -1, 3, -7, 100]:
        for op in range(5):
            scal(op, nz, x)
    binop(0, ta.array([1, big, 3], ta.int32), ta.array([1, 1, 1], ta.int32))
    binop(1, ta.array([0, small], ta.int32), ta.array([5, 1], ta.int32))
    binop(2, ta.array([2, 65536, 1], ta.int32), ta.array([3, 65536, 1], ta.int32))
    binop(3, ta.array([7, small], ta.int32), ta.array([2, -1], ta.int32))
    binop(4, ta.array([7, small, -7], ta.int32), ta.array([2, -1, 2], ta.int32))
    binop(3, ta.array([7, 8], ta.int32), ta.array([2, 0], ta.int32))
    binop(4, ta.array([7, 8], ta.int32), ta.array([0, 3], ta.int32))
    scal(0, ta.array([big], ta.int32), 1)
    scal(3, ta.array([5], ta.int32), 0)
    scal(4, ta.array([0], ta.int32), 5)
    unary(True, safe)
    unary(False, safe)
    unary(True, ta.array([1, big, small, 2], ta.int32))
    unary(False, ta.array([small], ta.int32))
    print("minimum int32|", ta.minimum(safe, nz), ta.minimum(safe, 2))
    print("maximum int32|", ta.maximum(safe, nz), ta.maximum(safe, -2))
    print("maximum int32|", ta.maximum(ta.array([small, big], ta.int32), ta.array([big, small], ta.int32)))
    p = ta.array([1, 2, big, 4], ta.int32)
    try:
        p += ta.array([10, 20, 1, 40], ta.int32)
    except OverflowError as e:
        print("add int32|", "OverflowError", e)
    print("add int32|", p)
    try:
        q = ta.array([1, 2], ta.int32) + ta.array([1, 2, 3], ta.int32)
        print(q)
    except ValueError as e:
        print("add int32|", "ValueError", e)
    try:
        print(ta.array([1], ta.int32) + 2147483648)
    except OverflowError as e:
        print("add int32|", "OverflowError", e)


main()
