from fractions import Fraction

SAMPLES = ["3/4", " -7/21 ", "0.125", "1e-3", "1.25e2", "+5", "1_000/2_5", ".5", "5.", "-.5", "  2 / 3  "]
BAD = ["", "abc", "1/0", "1.2.3", "3/", "1 / 2 / 3", "1e", "."]


def main():
    for text in SAMPLES:
        try:
            f = Fraction(text)
            print(repr(text), str(f), f.numerator, f.denominator)
        except (ValueError, ZeroDivisionError) as exc:
            print(repr(text), type(exc).__name__, str(exc))
    for text in BAD:
        try:
            print(repr(text), Fraction(text))
        except (ValueError, ZeroDivisionError) as exc:
            print(repr(text), type(exc).__name__, str(exc))
    for n, d in [(1, 0), (0, 0), (6, -8), (-6, -8), (Fraction(1, 2), Fraction(3, 4))]:
        try:
            print("pair", n, d, Fraction(n, d))
        except (ValueError, ZeroDivisionError, TypeError) as exc:
            print("pair", n, d, type(exc).__name__, str(exc))
    print(Fraction("1/2") == Fraction(2, 4))


main()
