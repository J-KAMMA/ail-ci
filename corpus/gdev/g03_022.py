# task: Implement a numerically stable softmax with maximum subtraction on a fixed vector and print probabilities that sum to one.
import math


def stable_softmax(values: list[float]) -> list[float]:
    """Compute softmax with maximum subtraction for numerical stability."""
    if not values:
        return []
    max_value: float = max(values)
    shifted: list[float] = [v - max_value for v in values]
    exps: list[float] = [math.exp(s) for s in shifted]
    total: float = math.fsum(exps)
    return [e / total for e in exps]


def main() -> None:
    values: list[float] = [1000.0, 1001.0, 1002.0, -500.0, 0.5]
    probabilities: list[float] = stable_softmax(values)

    print("Input values:", values)
    for index, (value, prob) in enumerate(zip(values, probabilities)):
        print(f"index={index} value={value:>10.2f} probability={prob:.12f}")

    total: float = math.fsum(probabilities)
    print(f"Sum of probabilities: {total:.12f}")
    print(f"Sums to one: {math.isclose(total, 1.0, rel_tol=1e-12, abs_tol=1e-12)}")


if __name__ == "__main__":
    main()
