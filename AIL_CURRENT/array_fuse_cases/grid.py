import math
import ail_array as ta


def digest(r: ta.Array[ta.f64]) -> str:
    data = r.tobytes()
    h = 0
    for i in range(len(data)):
        h = (h * 31 + data[i]) % 1000000007
    return str(len(r)) + ":" + str(h)


def triple(which: int, vals: list[float]) -> ta.Array[ta.f64]:
    m = len(vals)
    r = ta.zeros(m * m * m, ta.f64)
    for i in range(m * m * m):
        if which == 0:
            r[i] = vals[i // (m * m)]
        elif which == 1:
            r[i] = vals[(i // m) % m]
        else:
            r[i] = vals[i % m]
    return r


def p0(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a + b) + c


def p1(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a + (b + c)


def p2(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a + b) - c


def p3(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a + (b - c)


def p4(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a + b) * c


def p5(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a + (b * c)


def p6(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a + b) / c


def p7(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a + (b / c)


def p8(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a - b) + c


def p9(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a - (b + c)


def p10(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a - b) - c


def p11(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a - (b - c)


def p12(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a - b) * c


def p13(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a - (b * c)


def p14(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a - b) / c


def p15(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a - (b / c)


def p16(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a * b) + c


def p17(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a * (b + c)


def p18(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a * b) - c


def p19(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a * (b - c)


def p20(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a * b) * c


def p21(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a * (b * c)


def p22(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a * b) / c


def p23(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a * (b / c)


def p24(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a / b) + c


def p25(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a / (b + c)


def p26(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a / b) - c


def p27(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a / (b - c)


def p28(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a / b) * c


def p29(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a / (b * c)


def p30(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a / b) / c


def p31(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a / (b / c)


def p32(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return -(a * b) - c


def p33(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return abs(a - b) / c


def p34(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return abs(a / b) - abs(c)


def p35(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return -abs(a) * b


def p36(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return ta.minimum(a, b) + c


def p37(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return ta.maximum(a * b, c) - a


def p38(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return ta.minimum(a / b, ta.maximum(b, c))


def p39(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return ta.clip(a, b, c)


def p40(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return ta.clip(a + b, -1.0, 1.0) / c


def p41(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return ta.minimum(a, b)


def p42(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return ta.maximum(a, ta.minimum(b, c))


def p43(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a * b) / (c * a)


def p44(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return a / (b - b)


def p45(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return (a - a) / b


def p46(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return abs(a * b + c)


def p47(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return -(a / b / c)


def q0(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float) -> ta.Array[ta.f64]:
    return a * s + b


def q1(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float) -> ta.Array[ta.f64]:
    return a / s - b


def q2(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float) -> ta.Array[ta.f64]:
    return s / a + b * c


def q3(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float) -> ta.Array[ta.f64]:
    return ta.minimum(a, s) + b


def q4(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float) -> ta.Array[ta.f64]:
    return ta.maximum(a, 0.0) * s


def q5(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float) -> ta.Array[ta.f64]:
    return ta.clip(a + b, -s, s) * c


def q6(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float) -> ta.Array[ta.f64]:
    return (a + s) * (b - s)


def q7(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float) -> ta.Array[ta.f64]:
    return abs(a - s) / b


def q8(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float) -> ta.Array[ta.f64]:
    return a / s / b


def q9(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float) -> ta.Array[ta.f64]:
    return s - a * b


def r0(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> float:
    return ta.sum(a * b / c)


def r1(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> float:
    return ta.dot(a - b, ta.minimum(b, c) + a)


def r2(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> float:
    return ta.sum(ta.clip(a, b, c))


def i0(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    w = a.copy()
    w += b / c
    return w


def i1(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    w = a.copy()
    w -= abs(b) * c
    return w


def i2(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    w = a.copy()
    w /= ta.maximum(b, c) - a
    return w


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def main():
    vals = [math.inf, -math.inf, math.nan, -0.0, 0.0, 1.0, -1.0, 2.5, 1e308, -1e308, 1e-310, 5e-324, 3.0, -0.5]
    svals = [math.inf, math.nan, -0.0, 0.0, 2.5, -1e308, 5e-324]
    a = triple(0, vals)
    b = triple(1, vals)
    c = triple(2, vals)
    print("p0", digest(p0(a, b, c)))
    print("p1", digest(p1(a, b, c)))
    print("p2", digest(p2(a, b, c)))
    print("p3", digest(p3(a, b, c)))
    print("p4", digest(p4(a, b, c)))
    print("p5", digest(p5(a, b, c)))
    print("p6", digest(p6(a, b, c)))
    print("p7", digest(p7(a, b, c)))
    print("p8", digest(p8(a, b, c)))
    print("p9", digest(p9(a, b, c)))
    print("p10", digest(p10(a, b, c)))
    print("p11", digest(p11(a, b, c)))
    print("p12", digest(p12(a, b, c)))
    print("p13", digest(p13(a, b, c)))
    print("p14", digest(p14(a, b, c)))
    print("p15", digest(p15(a, b, c)))
    print("p16", digest(p16(a, b, c)))
    print("p17", digest(p17(a, b, c)))
    print("p18", digest(p18(a, b, c)))
    print("p19", digest(p19(a, b, c)))
    print("p20", digest(p20(a, b, c)))
    print("p21", digest(p21(a, b, c)))
    print("p22", digest(p22(a, b, c)))
    print("p23", digest(p23(a, b, c)))
    print("p24", digest(p24(a, b, c)))
    print("p25", digest(p25(a, b, c)))
    print("p26", digest(p26(a, b, c)))
    print("p27", digest(p27(a, b, c)))
    print("p28", digest(p28(a, b, c)))
    print("p29", digest(p29(a, b, c)))
    print("p30", digest(p30(a, b, c)))
    print("p31", digest(p31(a, b, c)))
    print("p32", digest(p32(a, b, c)))
    print("p33", digest(p33(a, b, c)))
    print("p34", digest(p34(a, b, c)))
    print("p35", digest(p35(a, b, c)))
    print("p36", digest(p36(a, b, c)))
    print("p37", digest(p37(a, b, c)))
    print("p38", digest(p38(a, b, c)))
    print("p39", digest(p39(a, b, c)))
    print("p40", digest(p40(a, b, c)))
    print("p41", digest(p41(a, b, c)))
    print("p42", digest(p42(a, b, c)))
    print("p43", digest(p43(a, b, c)))
    print("p44", digest(p44(a, b, c)))
    print("p45", digest(p45(a, b, c)))
    print("p46", digest(p46(a, b, c)))
    print("p47", digest(p47(a, b, c)))
    for s in svals:
        print("q0", s, digest(q0(a, b, c, s)))
        print("q1", s, digest(q1(a, b, c, s)))
        print("q2", s, digest(q2(a, b, c, s)))
        print("q3", s, digest(q3(a, b, c, s)))
        print("q4", s, digest(q4(a, b, c, s)))
        print("q5", s, digest(q5(a, b, c, s)))
        print("q6", s, digest(q6(a, b, c, s)))
        print("q7", s, digest(q7(a, b, c, s)))
        print("q8", s, digest(q8(a, b, c, s)))
        print("q9", s, digest(q9(a, b, c, s)))
    print("r0", bits(r0(a, b, c)), bits(r0(b, c, a)), bits(r0(c, a, b)))
    print("r1", bits(r1(a, b, c)), bits(r1(b, c, a)), bits(r1(c, a, b)))
    print("r2", bits(r2(a, b, c)), bits(r2(b, c, a)), bits(r2(c, a, b)))
    print("i0", digest(i0(a, b, c)), digest(i0(c, b, a)))
    print("i1", digest(i1(a, b, c)), digest(i1(c, b, a)))
    print("i2", digest(i2(a, b, c)), digest(i2(c, b, a)))


main()
