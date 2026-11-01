from fractions import Fraction


def approx(x, max_den):
    return x.limit_denominator(max_den)


def continued(x, n):
    out = []
    for _ in range(n):
        a = x.numerator // x.denominator
        out.append(a)
        rest = x - a
        if rest == 0:
            break
        x = 1 / rest
    return out


def main():
    pi = Fraction(355, 113)
    e = Fraction(271828, 100000)
    for den in [1, 2, 5, 10, 100, 1000, 1000000]:
        print("pi", den, approx(pi, den), float(approx(pi, den)))
    for den in [1, 2, 5, 10, 100, 1000, 1000000]:
        print("e", den, approx(e, den), float(approx(e, den)))
    print(continued(pi, 10))
    print(continued(e, 8))
    a = Fraction(0)
    for k in range(1, 21):
        a = a + Fraction(1, k)
    print(a, float(a), a.limit_denominator(100))
    b = Fraction(1)
    for k in range(1, 15):
        b = Fraction(1) / (1 + b)
    print(b, b.limit_denominator(1000))


main()
