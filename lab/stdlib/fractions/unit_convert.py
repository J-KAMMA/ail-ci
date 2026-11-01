from fractions import Fraction
import sys

FACTORS = {"inch": Fraction(1, 12), "foot": Fraction(1), "yard": Fraction(3), "mile": Fraction(5280)}


def to_feet(amount, unit):
    return amount * FACTORS[unit]


def main():
    count = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            print("bad", line)
            continue
        try:
            amount = Fraction(parts[0])
        except (ValueError, ZeroDivisionError) as exc:
            print("bad", line, type(exc).__name__)
            continue
        unit = parts[1]
        if unit not in FACTORS:
            print("unknown", unit)
            continue
        print(amount, unit, to_feet(amount, unit))
        count = count + 1
    if count == 0:
        print("no conversions")
    else:
        print("done", count)


main()
