import ail_array as ta


def digest(r: ta.Array[ta.f64]) -> str:
    n = len(r)
    data = r.tobytes()
    h = 0
    for i in range(len(data)):
        h = (h * 31 + data[i]) % 1000000007
    return str(n) + ":" + str(h)


def g(tag: str, a: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    print("g", tag)
    return a


def h(tag: str, s: float) -> float:
    print("h", tag)
    return s


def main():
    x = ta.array([1.0, 2.0, 3.0, 4.0, 5.0], ta.f64)
    y = ta.array([0.5, 1.5, 2.5, 3.5, 4.5, 5.5], ta.f64)
    z = ta.array([2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0], ta.f64)
    # a call among the operands: evaluated where it stood, in order, and the first failing check wins
    try:
        r = g("a", x) * g("b", y) + g("c", z)
        print(digest(r))
    except ValueError as e:
        print("ValueError", e)
    try:
        r = x * x + g("c", z) / g("d", y)
        print(digest(r))
    except ValueError as e:
        print("ValueError", e)
    try:
        r = abs(x - g("a", x)) + g("b", y) * x
        print(digest(r))
    except ValueError as e:
        print("ValueError", e)
    try:
        r = x + y * z + g("last", x)
        print(digest(r))
    except ValueError as e:
        print("ValueError", e)
    try:
        s = ta.sum(g("a", x) * g("b", y))
        print(s)
    except ValueError as e:
        print("ValueError", e)
    try:
        s = ta.sum(g("a", x) * g("b", x) + x)
        print(s)
    except ValueError as e:
        print("ValueError", e)
    try:
        s = ta.dot(g("a", x), x * x)
        print(s)
    except ValueError as e:
        print("ValueError", e)
    try:
        s = ta.dot(x * x, g("a", y))
        print(s)
    except ValueError as e:
        print("ValueError", e)
    try:
        s = ta.dot(g("p", x), g("q", y) / y)
        print(s)
    except ValueError as e:
        print("ValueError", e)
    try:
        w = x.copy()
        w += g("a", y) * y
        print(digest(w))
    except ValueError as e:
        print("ValueError", e)
    try:
        w = x.copy()
        w += x * g("a", x)
        print(digest(w))
        w -= g("b", x) * x
        print(digest(w))
    except ValueError as e:
        print("ValueError", e)
    # a scalar operand that is a call
    u = ta.array([1.0, 2.0, 3.0], ta.f64)
    print(digest(u * h("s", 2.0) + u))
    print(digest(u / h("t", 4.0) - u * h("v", 0.5)))
    print(h("u", 1.0) * ta.sum(u * u), ta.dot(u, u + u * h("w", 3.0)))


main()
