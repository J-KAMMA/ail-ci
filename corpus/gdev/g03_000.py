# task: Compute the mean, median, and mode of a hardcoded list of floats and print each result rounded to four decimal places.
import statistics


def main() -> None:
    data: list[float] = [1.5, 2.25, 3.0, 2.25, 4.75, 3.0, 2.25, 5.5, 6.125, 7.0]

    mean_value: float = statistics.mean(data)
    median_value: float = statistics.median(data)
    # multimode returns modes in order of first appearance, so output is deterministic.
    modes: list[float] = statistics.multimode(data)

    print(f"Mean: {mean_value:.4f}")
    print(f"Median: {median_value:.4f}")
    print("Mode: " + ", ".join(f"{m:.4f}" for m in modes))


if __name__ == "__main__":
    main()
