# task: Compute the dot product of two hard-coded vectors represented as Python lists and print the result.
from typing import Sequence


def dot_product(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("vectors must have the same length")
    return sum(x * y for x, y in zip(a, b))


def main() -> None:
    vector_a: list[float] = [1.0, 2.5, -3.0, 4.0, 0.5]
    vector_b: list[float] = [2.0, -1.0, 0.5, 3.0, 4.0]
    result = dot_product(vector_a, vector_b)
    print(f"Dot product: {result}")


if __name__ == "__main__":
    main()
