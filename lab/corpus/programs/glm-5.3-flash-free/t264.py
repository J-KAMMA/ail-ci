import sys
from math import sqrt
from typing import Literal

Kind = Literal["equilateral", "isosceles", "scalene", "invalid"]


def classify(a: int, b: int, c: int) -> Kind:
    if a + b <= c or b + c <= a or c + a <= b:
        return "invalid"
    if a == b == c:
        return "equilateral"
    if a == b or b == c or c == a:
        return "isosceles"
    return "scalene"


def heron_area(a: int, b: int, c: int) -> float:
    product = (a + b + c) * (-a + b + c) * (a - b + c) * (a + b - c)
    return sqrt(product) / 4.0


def main() -> None:
    for line in sys.stdin:
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        kind = classify(a, b, c)
        if kind == "invalid":
            print("invalid")
        else:
            print(f"{kind} {heron_area(a, b, c):.3f}")


if __name__ == "__main__":
    main()
