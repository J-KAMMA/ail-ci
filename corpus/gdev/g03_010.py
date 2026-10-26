# task: Compute the Pearson correlation coefficient between two fixed lists of floats from first principles and print it.
import math
from typing import Sequence


def mean(values: Sequence[float]) -> float:
    """Return the arithmetic mean of a non-empty sequence."""
    if not values:
        raise ValueError("mean() requires a non-empty sequence")
    return sum(values) / len(values)


def pearson_correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Compute the Pearson correlation coefficient from first principles.

    r = sum((x - mx) * (y - my)) / sqrt(sum((x - mx)^2) * sum((y - my)^2))
    """
    if len(xs) != len(ys):
        raise ValueError("sequences must have the same length")
    if len(xs) < 2:
        raise ValueError("at least two data points are required")

    mx = mean(xs)
    my = mean(ys)

    cov = 0.0
    var_x = 0.0
    var_y = 0.0
    for x, y in zip(xs, ys):
        dx = x - mx
        dy = y - my
        cov += dx * dy
        var_x += dx * dx
        var_y += dy * dy

    if var_x == 0.0 or var_y == 0.0:
        raise ValueError("correlation is undefined for constant input")

    return cov / math.sqrt(var_x * var_y)


def main() -> None:
    x_values: list[float] = [1.2, 2.3, 3.1, 4.8, 5.0, 6.7, 7.4, 8.9, 9.6, 10.2]
    y_values: list[float] = [2.0, 2.9, 3.7, 5.1, 5.6, 7.2, 7.9, 9.5, 9.9, 11.0]

    r = pearson_correlation(x_values, y_values)
    print(f"Pearson correlation coefficient: {r:.6f}")


if __name__ == "__main__":
    main()
