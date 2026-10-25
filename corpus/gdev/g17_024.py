# task: Use functools.partial to build a family of power functions and map them over a fixed base value.
from functools import partial
from typing import Callable


def power(base: float, exponent: float) -> float:
    """Return base raised to exponent."""
    return base ** exponent


def make_power_family(exponents: list[float]) -> list[Callable[[float], float]]:
    """Build a family of power functions, one per exponent, using partial.

    Each returned callable takes a base value and raises it to a fixed exponent.
    """
    return [partial(power, exponent=e) for e in exponents]


def main() -> None:
    exponents: list[float] = [0, 1, 2, 3, 0.5, -1]
    fixed_base: float = 2.0

    family = make_power_family(exponents)

    # Map each partial function over the fixed base value.
    results: list[float] = list(map(lambda f: f(fixed_base), family))

    print(f"Fixed base: {fixed_base}")
    for e, r in zip(exponents, results):
        print(f"  {fixed_base} ** {e} = {r}")

    # Also demonstrate the partial objects directly via map.
    squares_and_cubes = list(map(partial(power, exponent=2), [1.0, 2.0, 3.0, 4.0]))
    print(f"Squares of [1, 2, 3, 4]: {squares_and_cubes}")


if __name__ == "__main__":
    main()
