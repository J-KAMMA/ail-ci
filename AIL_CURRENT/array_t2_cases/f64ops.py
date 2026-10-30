import math
import ail_array as ta


def show(label: str, a: ta.Array[ta.f64]):
    print(label, a, a.tobytes().hex())


def bits(label: str, x: float):
    print(label, x, ta.array([x], ta.f64).tobytes().hex(), math.copysign(1.0, x))


def main():
    inf = math.inf
    nan = math.nan
    tiny = 5e-324
    big = 1.7976931348623157e308
    xs = ta.array([0.0, -0.0, 1.0, -1.0, 0.1, tiny, -tiny, big, -big, inf, -inf, nan, 2.5, 3], ta.f64)
    ys = ta.array([0.0, 0.0, -0.0, 3.0, 0.2, tiny, tiny, big, big, inf, inf, 1.0, nan, 0], ta.f64)
    show("add", xs + ys)
    show("sub", xs - ys)
    show("mul", xs * ys)
    show("div", xs / ys)
    show("neg", -xs)
    show("abs", abs(xs))
    show("adds", xs + 1.5)
    show("subs", xs - 1)
    show("muls", xs * 2)
    show("divs", xs / 0.0)
    show("divs0", xs / 3)
    show("radd", 1.5 + xs)
    show("rsub", 10 - xs)
    show("rmul", 0.5 * xs)
    show("rdiv", 1.0 / xs)
    show("rdiv0", 0.0 / xs)
    show("divnan", xs / nan)
    z = xs + ys
    bits("inf-inf", ta.sum(ta.array([inf, -inf], ta.f64)))
    bits("nan sign", z[11])
    w = ta.array([inf, 1.0], ta.f64) - ta.array([inf, 1.0], ta.f64)
    bits("w0", w[0])
    bits("w1", w[1])
    # in-place
    p = xs.copy()
    p += ys
    show("iadd", p)
    p -= 2
    show("isub", p)
    p *= xs
    show("imul", p)
    p /= 3.5
    show("idiv", p)
    q = p
    q += 1.0
    show("alias", p)
    print(p is q)
    # min / max / clip
    show("minimum", ta.minimum(xs, ys))
    show("maximum", ta.maximum(xs, ys))
    show("minimum_s", ta.minimum(xs, 0.0))
    show("maximum_s", ta.maximum(xs, -0.0))
    show("clip", ta.clip(xs, -1.0, 2.0))
    show("clipn", ta.clip(xs, nan, 2.0))
    # math functions
    m = ta.array([0.0, -0.0, 1.0, -1.0, 4.0, 2.0, 1e-300, 709.0, 709.782712893384, 709.78271289338409, 710.0, 1e308, -745.0, -746.0, inf, -inf, nan, 0.5, 100.0, 1e-10], ta.f64)
    show("sqrt", ta.sqrt(m))
    show("exp", ta.exp(m))
    show("log", ta.log(m))
    show("tanh", ta.tanh(m))
    # reductions
    print(ta.sum(xs), ta.dot(xs, ys), ta.min(xs), ta.max(xs), ta.argmin(xs), ta.argmax(xs))
    r = ta.array([3.0, -0.0, 0.0, 2.0, -5.0, 2.0, -5.0, 3.0], ta.f64)
    print(ta.min(r), ta.max(r), ta.argmin(r), ta.argmax(r))
    r2 = ta.array([-0.0, 0.0, -0.0], ta.f64)
    print(ta.min(r2), ta.max(r2), ta.argmin(r2), ta.argmax(r2))
    r3 = ta.array([1.0, nan, 0.0, nan], ta.f64)
    print(ta.min(r3), ta.max(r3), ta.argmin(r3), ta.argmax(r3))
    bits("sum -0", ta.sum(ta.array([-0.0], ta.f64)))
    bits("sum -0 -0", ta.sum(ta.array([-0.0, -0.0], ta.f64)))
    bits("sum 0 -0", ta.sum(ta.array([0.0, -0.0], ta.f64)))
    bits("sum empty", ta.sum(ta.zeros(0, ta.f64)))
    bits("dot empty", ta.dot(ta.zeros(0, ta.f64), ta.zeros(0, ta.f64)))
    # casts
    c = ta.array([0.0, -0.0, 0.5, 1.5, 2.5, -0.5, -1.5, -2.5, 2147483647.0, -2147483648.0, -2147483648.5, 0.9999999, 1e9], ta.f64)
    print(c.astype(ta.int32), c.astype(ta.int32, 'nearest'))
    d = ta.array([2147483648.0, 3e9, -2147483649.0, 4294967296.0, -4294967296.0, 1e300, inf, -inf, nan, 2.5], ta.f64)
    print(d.astype(ta.int32, 'trunc', 'saturate'), d.astype(ta.int32, 'nearest', 'saturate'))
    for k in range(len(d)):
        try:
            one = ta.array([d[k]], ta.f64)
            print(k, one.astype(ta.int32))
        except OverflowError as exc:
            print(k, "OverflowError", exc)
        except ValueError as exc:
            print(k, "ValueError", exc)
    try:
        print(c.astype(ta.int32, 'trunc', 'wrap'))
    except ValueError as exc:
        print("ValueError", exc)
    show("f2f", c.astype(ta.f64))
    # mixed dtype, shapes
    try:
        show("shape", xs + ta.zeros(3, ta.f64))
    except ValueError as exc:
        print("ValueError", exc)
    try:
        ta.dot(xs, ta.zeros(3, ta.f64))
    except ValueError as exc:
        print("ValueError", exc)
    try:
        ta.min(ta.zeros(0, ta.f64))
    except ValueError as exc:
        print("ValueError", exc)
    try:
        ta.argmax(ta.zeros(0, ta.f64))
    except ValueError as exc:
        print("ValueError", exc)


main()
