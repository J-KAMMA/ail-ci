# task: Parse embedded 'HH:MM:SS event' lines and print the longest gap in minutes between consecutive events.
from __future__ import annotations

from dataclasses import dataclass

EVENTS_TEXT = """
08:00:00 login alice
08:14:30 upload report.csv
08:15:05 logout alice
09:02:10 login bob
09:03:45 query sales
09:04:00 logout bob
11:30:00 login carol
11:31:15 delete temp.dat
11:31:20 logout carol
12:00:00 backup start
12:05:30 backup end
"""


@dataclass(frozen=True)
class Event:
    seconds: int
    name: str


def parse_time(text: str) -> int:
    hours, minutes, seconds = (int(part) for part in text.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def parse_events(text: str) -> list[Event]:
    events: list[Event] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        time_part, _, name = line.partition(" ")
        events.append(Event(parse_time(time_part), name.strip()))
    events.sort(key=lambda e: (e.seconds, e.name))
    return events


def longest_gap(events: list[Event]) -> tuple[int, Event, Event] | None:
    best: tuple[int, Event, Event] | None = None
    for previous, following in zip(events, events[1:]):
        gap = following.seconds - previous.seconds
        if best is None or gap > best[0]:
            best = (gap, previous, following)
    return best


def format_clock(total_seconds: int) -> str:
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def main() -> None:
    events = parse_events(EVENTS_TEXT)
    if len(events) < 2:
        print("Need at least two events to compute a gap.")
        return

    result = longest_gap(events)
    if result is None:
        print("No gap found.")
        return

    gap_seconds, start, end = result
    print(f"Longest gap: {gap_seconds / 60:.2f} minutes")
    print(f"From {format_clock(start.seconds)} ({start.name})")
    print(f"To   {format_clock(end.seconds)} ({end.name})")


if __name__ == "__main__":
    main()
