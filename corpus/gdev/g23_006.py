# task: Normalize a hard-coded vector to unit length and print each component rounded to three decimals.
import math


def normalize(vector: list[float]) -> list[float]:
    """Return the unit-length version of a non-zero vector."""
    norm: float = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        raise ValueError("cannot normalize a zero-length vector")
    return [component / norm for component in vector]


def main() -> None:
    vector: list[float] = [3.0, 4.0, 12.0]
    unit: list[float] = normalize(vector)
    for component in unit:
        print(f"{component:.3f}")


if __name__ == "__main__":
    main()
