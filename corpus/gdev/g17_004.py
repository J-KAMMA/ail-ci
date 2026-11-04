# task: Use functools.partial to create a scaling function and apply it to a list of numbers with map.
from functools import partial


def scale(factor: float, value: float) -> float:
    """Multiply a value by the given factor."""
    return factor * value


def main() -> None:
    numbers: list[float] = [1, 2, 3, 4.5, -2, 10]

    double = partial(scale, 2)
    triple = partial(scale, 3)
    half = partial(scale, 0.5)

    print("Original:", numbers)
    print("Doubled: ", list(map(double, numbers)))
    print("Tripled: ", list(map(triple, numbers)))
    print("Halved:  ", list(map(half, numbers)))


if __name__ == "__main__":
    main()
