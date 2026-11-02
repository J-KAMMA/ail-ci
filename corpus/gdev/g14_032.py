# task: Create a dataclass Event with datetime fields constructed from fixed dates and compute durations between them.
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Event:
    name: str
    start: datetime
    end: datetime

    def duration(self) -> timedelta:
        return self.end - self.start

    def duration_hours(self) -> float:
        return self.duration().total_seconds() / 3600.0


def format_timedelta(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"


def build_events() -> list[Event]:
    return [
        Event(
            name="Project kickoff",
            start=datetime(2024, 1, 15, 9, 0),
            end=datetime(2024, 1, 15, 17, 30),
        ),
        Event(
            name="Sprint 1",
            start=datetime(2024, 1, 22, 8, 0),
            end=datetime(2024, 2, 5, 18, 0),
        ),
        Event(
            name="Leap day release",
            start=datetime(2024, 2, 28, 12, 0),
            end=datetime(2024, 3, 1, 12, 0),
        ),
        Event(
            name="Year-end review",
            start=datetime(2023, 12, 29, 10, 0),
            end=datetime(2024, 1, 2, 16, 45),
        ),
    ]


def main() -> None:
    events = build_events()

    print("Event durations:")
    for event in events:
        delta = event.duration()
        print(
            f"  {event.name}: {event.start:%Y-%m-%d %H:%M} -> "
            f"{event.end:%Y-%m-%d %H:%M} | "
            f"{format_timedelta(delta)} ({event.duration_hours():.2f} h)"
        )

    total = sum((e.duration() for e in events), timedelta())
    print(f"\nTotal across all events: {format_timedelta(total)}")

    longest = max(events, key=lambda e: e.duration())
    shortest = min(events, key=lambda e: e.duration())
    print(f"Longest event: {longest.name}")
    print(f"Shortest event: {shortest.name}")

    first = min(events, key=lambda e: e.start)
    last = max(events, key=lambda e: e.end)
    gap = first.end - last.start
    print(f"\nEarliest start: {first.name} at {first.start:%Y-%m-%d %H:%M}")
    print(f"Latest end: {last.name} at {last.end:%Y-%m-%d %H:%M}")
    print(f"Span from earliest start to latest end: "
          f"{format_timedelta(last.end - first.start)}")
    print(f"Gap between first event end and last event start: "
          f"{format_timedelta(gap)}")


if __name__ == "__main__":
    main()
