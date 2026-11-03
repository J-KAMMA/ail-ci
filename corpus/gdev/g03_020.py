# task: Compute a simple moving average with window size five over a deterministic sine-based series and print the resulting values.
import math


def sine_series(n: int, step: float = 0.1) -> list[float]:
    """Generate a deterministic sine-based series of length n."""
    return [math.sin(i * step) for i in range(n)]


def simple_moving_average(values: list[float], window: int) -> list[float]:
    """Compute the simple moving average with the given window size."""
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        return []
    result: list[float] = []
    running_sum = sum(values[:window])
    result.append(running_sum / window)
    for i in range(window, len(values)):
        running_sum += values[i] - values[i - window]
        result.append(running_sum / window)
    return result


def main() -> None:
    window_size = 5
    series = sine_series(30)
    averages = simple_moving_average(series, window_size)

    print(f"Series length: {len(series)}")
    print(f"Window size: {window_size}")
    print("Simple moving averages:")
    for index, avg in enumerate(averages):
        print(f"  [{index:2d}] {avg:.6f}")


if __name__ == "__main__":
    main()
