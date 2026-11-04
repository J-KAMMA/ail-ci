# task: Convert a list of fixed durations given in total seconds into human-readable strings like '2 days, 3 hours, 4 minutes'.
from typing import Final

SECONDS_PER_UNIT: Final[tuple[tuple[str, int], ...]] = (
    ("day", 86_400),
    ("hour", 3_600),
    ("minute", 60),
    ("second", 1),
)

DURATIONS_IN_SECONDS: Final[tuple[int, ...]] = (
    0,
    1,
    59,
    60,
    3_600,
    3_661,
    90_000,
    183_845,
    604_800,
    694_861,
)


def format_duration(total_seconds: int) -> str:
    """Convert a non-negative number of seconds into a readable string."""
    if total_seconds < 0:
        raise ValueError("duration must be non-negative")

    parts: list[str] = []
    remaining: int = total_seconds
    for name, size in SECONDS_PER_UNIT:
        count, remaining = divmod(remaining, size)
        if count:
            suffix = "" if count == 1 else "s"
            parts.append(f"{count} {name}{suffix}")

    if not parts:
        return "0 seconds"
    return ", ".join(parts)


def main() -> None:
    for seconds in DURATIONS_IN_SECONDS:
        print(f"{seconds:>10} s -> {format_duration(seconds)}")


if __name__ == "__main__":
    main()
