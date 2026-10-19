import sys


MINUTES_PER_DAY = 24 * 60


def parse_time(text: str) -> int:
    """Convert an HH:MM string to minutes since midnight."""
    hours_str, minutes_str = text.strip().split(":")
    return int(hours_str) * 60 + int(minutes_str)


def largest_circular_gap(sorted_minutes: list[int]) -> int:
    """Return the largest gap between consecutive times, wrapping over midnight."""
    if len(sorted_minutes) == 1:
        return MINUTES_PER_DAY
    gaps = [
        sorted_minutes[i + 1] - sorted_minutes[i]
        for i in range(len(sorted_minutes) - 1)
    ]
    gaps.append(sorted_minutes[0] + MINUTES_PER_DAY - sorted_minutes[-1])
    return max(gaps)


def main() -> None:
    times: list[int] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        times.append(parse_time(line))

    if not times:
        return

    times.sort()
    print(" ".join(str(m) for m in times))
    print(largest_circular_gap(times))


if __name__ == "__main__":
    main()
