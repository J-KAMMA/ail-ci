# Element-wise operations on 2-D f32 arrays (job aicore1): every operator, scalars on both sides, in place, unary, the math
# functions and minimum / maximum / clip, with specials; each result printed with its bytes.
import math
import ail_array as ta


def show(cell: str, m: ta.Matrix[ta.f32]):
    r, c = m.shape
    print(cell + "|", m, r, c, m.tobytes().hex())


def main():
    a = ta.array([[0.0, -0.0, 1.0, -1.0, 0.1], [-2.5, 1e-45, 16777217.0, 3.4028234663852886e+38, 1e39],
                  [math.inf, -math.inf, math.nan, 0.5, 3.0]], ta.f32)
    b = ta.array([[3.0, 7.0, -0.0, 0.1, 2.0], [0.0, 1e-30, 3.0, 3.4028234663852886e+38, -1.0],
                  [math.inf, 1.0, 2.0, math.nan, 1e-38]], ta.f32)
    show("add", a + b)
    show("sub", a - b)
    show("mul", a * b)
    show("div", a / b)
    show("add s", a + 0.1)
    show("rsub s", 0.1 - a)
    show("mul s", a * 3)
    show("rdiv s", 1.0 / a)
    show("div s", a / 0.0)
    show("neg", -a)
    show("abs", abs(a))
    show("sqrt", ta.sqrt(abs(a)))
    show("exp", ta.exp(a))
    show("log", ta.log(a))
    show("tanh", ta.tanh(a))
    show("max s", ta.maximum(a, 0.0))
    show("min", ta.minimum(a, b))
    show("clip", ta.clip(a, -1.0, 1.0))
    c = a.copy()
    c += b
    c *= 0.5
    c -= a
    c /= b
    show("inplace", c)
    show("chain", (a * b + a) / (b - 2.0))
    t = (a + 0.0).T
    r, k = t.shape
    print(a == a.copy(), a == b, r, k, ta.sum((a * 2.0)[1]))


main()
