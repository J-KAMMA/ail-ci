import math
import ail_array as ta

DATA = ta.array([3.0, 1.0, 2.0], ta.f64)
COUNTS = ta.arange(4, ta.int32)


def scale(a, k):
    return a * k


def fill(a: ta.Array[ta.f64], v: float):
    for i in range(len(a)):
        a[i] = v + i


def bump(a: ta.Array[ta.int32]) -> ta.Array[ta.int32]:
    a += 1
    return a


def mk(n: int):
    return ta.zeros(n, ta.int32)


def norm2(a: ta.Array[ta.f64]) -> float:
    return math.sqrt(ta.dot(a, a))


def axpy(alpha: float, x: ta.Array[ta.f64], y: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return alpha * x + y


def total(a: ta.Array[ta.f64]) -> float:
    t = 0.0
    for i in range(len(a)):
        t += a[i]
    return t


def main():
    x = ta.array([1.0, 2.0, 3.0], ta.f64)
    y = scale(x, 2.0)
    print(x, y, DATA * 2, COUNTS * 3)
    fill(x, 0.5)
    print(x, y)
    z = mk(4)
    z[1] = 3
    print(bump(z), z, bump(bump(z)) is z)
    print(norm2(y), axpy(2.0, x, y), total(axpy(0.5, x, DATA)))
    w = x
    w[0] = -9.0
    print(x[0], w is x)
    # lists of results, conditional expressions, loops building arrays
    acc = ta.zeros(5, ta.f64)
    for k in range(5):
        acc[k] = float(k * k) if k % 2 == 0 else -1.0 * k
    big = acc if len(acc) > 3 else x
    print(big, [acc[k] for k in range(len(acc))], [v for v in acc if v > 0.0])
    s = 0
    for v in COUNTS:
        s += v
    print(s)
    # run-time type errors the reference raises
    try:
        print(x + z)
    except TypeError as exc:
        print("TypeError", exc)
    try:
        print(z + 1.5)
    except TypeError as exc:
        print("TypeError", exc)
    try:
        z[0] = 1.5
    except TypeError as exc:
        print("TypeError", exc)
    try:
        print(ta.minimum(z, 2.5))
    except TypeError as exc:
        print("TypeError", exc)
    try:
        print(ta.sqrt(z))
    except TypeError as exc:
        print("TypeError", exc)
    try:
        print(ta.wrapping_add(x, x))
    except TypeError as exc:
        print("TypeError", exc)
    try:
        print(ta.dot(x, z))
    except TypeError as exc:
        print("TypeError", exc)
    try:
        x[0:2] = z[0:2]
    except TypeError as exc:
        print("TypeError", exc)
    try:
        x[0:2] = [1.0, 2.0]
    except TypeError as exc:
        print("TypeError", exc)
    try:
        print(ta.sum(z, acc=ta.f64))
    except ValueError as exc:
        print("ValueError", exc)
    print(ta.sum(x, acc=ta.f64), ta.dot(x, x, order='any'), ta.sum(x, order='any'))
    print(x == z, z == x, x != z)


main()
