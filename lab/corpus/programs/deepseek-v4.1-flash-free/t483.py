import sys
from fractions import Fraction


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    numbers = data[1:1 + n]
    out = []
    for token in numbers:
        value = float(token)
        frac = Fraction(value).limit_denominator(100)
        out.append(f"{frac.numerator}/{frac.denominator}")
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
