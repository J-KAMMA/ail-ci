# task: Generate normally distributed values with a seeded random generator, bin them into a fixed number of buckets, and print an ASCII histogram.
import random
from typing import List


SEED: int = 42
SAMPLE_COUNT: int = 10_000
MEAN: float = 0.0
STD_DEV: float = 1.0
NUM_BUCKETS: int = 20
RANGE_LOW: float = -4.0
RANGE_HIGH: float = 4.0
BAR_WIDTH: int = 60
BAR_CHAR: str = "#"


def generate_samples(count: int, mean: float, std_dev: float) -> List[float]:
    """Return a list of normally distributed samples using the seeded RNG."""
    return [random.gauss(mean, std_dev) for _ in range(count)]


def bin_samples(samples: List[float], low: float, high: float, buckets: int) -> List[int]:
    """Count samples falling into equal-width buckets over [low, high)."""
    counts: List[int] = [0] * buckets
    width: float = (high - low) / buckets
    for value in samples:
        if value < low or value >= high:
            continue
        index: int = int((value - low) / width)
        if index >= buckets:
            index = buckets - 1
        counts[index] += 1
    return counts


def render_histogram(counts: List[int], low: float, high: float) -> List[str]:
    """Build ASCII histogram lines scaled to BAR_WIDTH."""
    buckets: int = len(counts)
    width: float = (high - low) / buckets
    max_count: int = max(counts) if counts else 0
    lines: List[str] = []
    for i, count in enumerate(counts):
        left: float = low + i * width
        right: float = left + width
        if max_count > 0:
            bar_len: int = round(count * BAR_WIDTH / max_count)
        else:
            bar_len = 0
        bar: str = BAR_CHAR * bar_len
        lines.append(f"[{left:6.2f}, {right:6.2f}) {count:6d} | {bar}")
    return lines


def main() -> None:
    random.seed(SEED)
    samples: List[float] = generate_samples(SAMPLE_COUNT, MEAN, STD_DEV)
    counts: List[int] = bin_samples(samples, RANGE_LOW, RANGE_HIGH, NUM_BUCKETS)

    total_binned: int = sum(counts)
    print(f"Normal distribution histogram (seed={SEED}, samples={SAMPLE_COUNT})")
    print(f"mean={MEAN}, std_dev={STD_DEV}, range=[{RANGE_LOW}, {RANGE_HIGH}), buckets={NUM_BUCKETS}")
    print("-" * 80)
    for line in render_histogram(counts, RANGE_LOW, RANGE_HIGH):
        print(line)
    print("-" * 80)
    print(f"Total binned: {total_binned} of {SAMPLE_COUNT}")


if __name__ == "__main__":
    main()
