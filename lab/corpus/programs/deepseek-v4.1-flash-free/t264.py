import math
import sys


def triangle_type(a: int, b: int, c: int) -> str:
    if a + b <= c or a + c <= b or b + c <= a:
        return "invalid"
    if a == b == c:
        return "equilateral"
    if a == b or b == c or a == c:
        return "isosceles"
    return "scalene"


def heron_area(a: int, b: int, c: int) -> float:
    s = (a + b + c) / 2
    return math.sqrt(s * (s - a) * (s - b) * (s - c))


def main() -> None:
    out = []
    for line in sys.stdin:
        parts = line.split()
        if len(parts) < 3:
            continue
        a, b, c = (int(p) for p in parts[:3])
        kind = triangle_type(a, b, c)
        if kind == "invalid":
            out.append("invalid")
        else:
            out.append(f"{kind} {heron_area(a, b, c):.3f}")
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


if __name__ == "__main__":
    main()
