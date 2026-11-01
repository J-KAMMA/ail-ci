# task: Compute the angle in degrees between two hard-coded vectors using the dot product and print it to two decimals.
import math
from typing import Sequence


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    """Return the dot product of two equal-length vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must have the same length")
    return sum(x * y for x, y in zip(a, b))


def norm(a: Sequence[float]) -> float:
    """Return the Euclidean norm of a vector."""
    return math.sqrt(dot(a, a))


def angle_degrees(a: Sequence[float], b: Sequence[float]) -> float:
    """Return the angle in degrees between two non-zero vectors."""
    na = norm(a)
    nb = norm(b)
    if na == 0 or nb == 0:
        raise ValueError("angle is undefined for zero-length vectors")
    cos_theta = dot(a, b) / (na * nb)
    # Clamp to [-1, 1] to guard against floating-point rounding errors.
    cos_theta = max(-1.0, min(1.0, cos_theta))
    return math.degrees(math.acos(cos_theta))


def main() -> None:
    v1: list[float] = [3.0, 4.0, 0.0]
    v2: list[float] = [4.0, -3.0, 5.0]
    theta = angle_degrees(v1, v2)
    print(f"{theta:.2f}")


if __name__ == "__main__":
    main()
