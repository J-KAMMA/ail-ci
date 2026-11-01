from datetime import datetime, timedelta


def parse(line: str) -> datetime:
    fields = line.split(" ")
    return datetime.fromisoformat(fields[0])


def main() -> None:
    lines = [
        "2024-03-10T08:15:00.250 boot",
        "2024-03-10T08:15:02.750 ready",
        "2024-03-10T08:16:10.000 request",
        "2024-03-10T08:16:10.125 request",
        "2024-03-10T08:17:45.900 stop",
    ]
    events: list[datetime] = []
    for line in lines:
        events.append(parse(line))
    events.sort()
    total = timedelta()
    previous = events[0]
    for event in events:
        gap = event - previous
        total += gap
        print(event.isoformat(timespec="milliseconds"), event.replace(microsecond=0),
              gap.total_seconds(), event.strftime("%H:%M:%S"))
        previous = event
    print("span", events[-1] - events[0], (events[-1] - events[0]).total_seconds())
    print("sum", total, total > timedelta(minutes=2))


main()
