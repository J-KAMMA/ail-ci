# task: Compute the chi-square goodness-of-fit statistic for fixed observed and expected category counts and print the statistic and degrees of freedom.
from typing import Sequence


def chi_square_statistic(observed: Sequence[float], expected: Sequence[float]) -> float:
    """Return the chi-square goodness-of-fit statistic sum((O - E)^2 / E)."""
    if len(observed) != len(expected):
        raise ValueError("observed and expected must have the same length")
    if len(observed) == 0:
        raise ValueError("at least one category is required")

    statistic = 0.0
    for obs, exp in zip(observed, expected):
        if exp <= 0:
            raise ValueError("expected counts must be positive")
        statistic += (obs - exp) ** 2 / exp
    return statistic


def degrees_of_freedom(num_categories: int) -> int:
    """Return degrees of freedom for a goodness-of-fit test with no estimated parameters."""
    return num_categories - 1


def main() -> None:
    categories: list[str] = ["A", "B", "C", "D"]
    observed: list[float] = [18, 22, 30, 30]
    expected: list[float] = [25, 25, 25, 25]

    statistic = chi_square_statistic(observed, expected)
    dof = degrees_of_freedom(len(categories))

    print(f"Categories: {', '.join(categories)}")
    print(f"Chi-square statistic: {statistic:.4f}")
    print(f"Degrees of freedom: {dof}")


if __name__ == "__main__":
    main()
