from fractions import Fraction

RATIOS = {
    "octave": (2, 1),
    "fifth": (3, 2),
    "fourth": (4, 3),
    "major third": (5, 4),
    "minor third": (6, 5),
}


def main():
    base = Fraction(440)
    for name in sorted(RATIOS):
        n, d = RATIOS[name]
        ratio = Fraction(n, d)
        f = base * ratio
        print(name, ratio, f, float(f), round(float(f), 2))
    up = Fraction(3, 2)
    down = 1 / up
    print("up", up, "down", down, up * down)
    stack = Fraction(1)
    for _ in range(12):
        stack = stack * Fraction(3, 2)
    print(stack, float(stack))
    tone = Fraction(9, 8)
    more = Fraction(10, 9)
    print(tone * more, tone / more, tone - more)
    total = Fraction(0)
    for k in [-2, -1, 0, 1, 2]:
        print(k, Fraction(3, 2) ** k)
        total = total + Fraction(3, 2) ** k
    print(total, total.limit_denominator(100))


main()
