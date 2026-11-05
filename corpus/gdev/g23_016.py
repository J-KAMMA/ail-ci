# task: Compute the projection of one hard-coded vector onto another and print the projected components.
import math
from typing import Sequence


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    """Return the dot product of two equal-length vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must have the same dimension")
    return sum(x * y for x, y in zip(a, b))


def project(u: Sequence[float], onto: Sequence[float]) -> list[float]:
    """Return the vector projection of u onto the vector 'onto'."""
    denom = dot(onto, onto)
    if denom == 0:
        raise ValueError("cannot project onto the zero vector")
    scale = dot(u, onto) / denom
    return [scale * c for c in onto]


def scalar_component(u: Sequence[float], onto: Sequence[float]) -> float:
    """Return the signed scalar component of u along 'onto'."""
    norm = math.sqrt(dot(onto, onto))
    if norm == 0:
        raise ValueError("cannot project onto the zero vector")
    return dot(u, onto) / norm


def format_vector(v: Sequence[float]) -> str:
    return "(" + ", ".join(f"{x:.4f}" for x in v) + ")"


def main() -> None:
    u: list[float] = [3.0, 4.0, 5.0]
    v: list[float] = [1.0, 2.0, 2.0]

    proj = project(u, v)
    scalar = scalar_component(u, v)
    perp = [a - b for a, b in zip(u, proj)]

    print(f"Vector u:              {format_vector(u)}")
    print(f"Vector onto (v):       {format_vector(v)}")
    print(f"Scalar component:      {scalar:.4f}")
    print(f"Projection of u on v:  {format_vector(proj)}")
    print(f"Orthogonal remainder:  {format_vector(perp)}")
    print(f"Check (remainder . v): {dot(perp, v):.4f}")


if __name__ == "__main__":
    main()
