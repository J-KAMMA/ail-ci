import math
import sys


def classify(a: int, b: int, c: int) -> str:
    """Return the triangle type for the given side lengths."""
    if a + b <= c or a + c <= b or b + c <= a:
        return "invalid"
    if a == b == c:
        return "equilateral"
    if a == b or b == c or a == c:
        return "isosceles"
    return "scalene"


def heron_area(a: int, b: int, c: int) -> float:
    """Compute the area with Heron's formula, using an exact integer product."""
    product = (a + b + c) * (-a + b + c) * (a - b + c) * (a + b - c)
    return math.sqrt(product) / 4.0


def main() -> None:
    out_lines: list[str] = []
    for line in sys.stdin:
        parts = line.split()
        if len(parts) != 3:
            continue
        a, b, c = (int(p) for p in parts)
        kind = classify(a, b, c)
        if kind == "invalid":
            out_lines.append("invalid")
        else:
            out_lines.append(f"{kind} {heron_area(a, b, c):.3f}")
    if out_lines:
        sys.stdout.write("\n".join(out_lines) + "\n")


if __name__ == "__main__":
    main()
