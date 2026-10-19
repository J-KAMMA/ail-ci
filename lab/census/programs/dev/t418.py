from fractions import Fraction
import sys


def main() -> None:
    data = sys.stdin.read().split()
    total = Fraction(0)
    for token in data:
        x = abs(int(token))
        if x == 0:
            continue
        total += Fraction(1, x)
    print(f"{total.numerator}/{total.denominator} {float(total):.10f}")


if __name__ == "__main__":
    main()
