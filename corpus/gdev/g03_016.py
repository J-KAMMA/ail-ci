# task: Compute the five-number summary of a fixed dataset using linear interpolation for quartiles and print the minimum, Q1, median, Q3, and maximum.
import math


def percentile_linear(sorted_data: list[float], p: float) -> float:
    """Return the p-th quantile (0 <= p <= 1) using linear interpolation.

    Uses the common "type 7" definition: position = p * (n - 1).
    """
    if not sorted_data:
        raise ValueError("cannot compute a percentile of empty data")
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be between 0 and 1")

    n: int = len(sorted_data)
    position: float = p * (n - 1)
    lower: int = math.floor(position)
    upper: int = math.ceil(position)
    fraction: float = position - lower

    lower_value: float = sorted_data[lower]
    upper_value: float = sorted_data[upper]
    return lower_value + (upper_value - lower_value) * fraction


def five_number_summary(data: list[float]) -> tuple[float, float, float, float, float]:
    """Return (minimum, Q1, median, Q3, maximum) for the given data."""
    ordered: list[float] = sorted(data)
    minimum: float = ordered[0]
    q1: float = percentile_linear(ordered, 0.25)
    median: float = percentile_linear(ordered, 0.50)
    q3: float = percentile_linear(ordered, 0.75)
    maximum: float = ordered[-1]
    return minimum, q1, median, q3, maximum


def main() -> None:
    dataset: list[float] = [
        7.0, 15.0, 36.0, 39.0, 40.0, 41.0, 42.0, 43.0, 47.0, 49.0, 52.5, 60.0,
    ]

    minimum, q1, median, q3, maximum = five_number_summary(dataset)

    print(f"Minimum: {minimum:.2f}")
    print(f"Q1:      {q1:.2f}")
    print(f"Median:  {median:.2f}")
    print(f"Q3:      {q3:.2f}")
    print(f"Maximum: {maximum:.2f}")


if __name__ == "__main__":
    main()
