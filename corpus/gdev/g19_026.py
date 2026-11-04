# task: Find the longest gap in days between consecutive dates from a fixed sorted list of dates and print the start and end of that gap.
from datetime import date


DATES: list[date] = [
    date(2023, 1, 3),
    date(2023, 1, 10),
    date(2023, 2, 1),
    date(2023, 2, 5),
    date(2023, 6, 30),
    date(2023, 7, 2),
    date(2023, 12, 25),
]


def longest_gap(dates: list[date]) -> tuple[date, date, int] | None:
    """Return (start, end, gap_days) for the longest gap between consecutive dates.

    Ties are resolved by taking the earliest such gap. Returns None if there
    are fewer than two dates.
    """
    ordered = sorted(dates)
    if len(ordered) < 2:
        return None

    best_start = ordered[0]
    best_end = ordered[1]
    best_days = (best_end - best_start).days

    for earlier, later in zip(ordered, ordered[1:]):
        gap = (later - earlier).days
        if gap > best_days:
            best_start, best_end, best_days = earlier, later, gap

    return best_start, best_end, best_days


def main() -> None:
    result = longest_gap(DATES)
    if result is None:
        print("Need at least two dates to compute a gap.")
        return

    start, end, days = result
    print(f"Longest gap: {days} days")
    print(f"Start: {start.isoformat()}")
    print(f"End: {end.isoformat()}")


if __name__ == "__main__":
    main()
