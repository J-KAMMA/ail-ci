from datetime import date, timedelta

ROTATION = ["alice", "bob", "carol", "dave"]


def main() -> None:
    start = date(2024, 4, 1)
    schedule: dict[date, str] = {}
    day = start
    shift = 0
    for i in range(14):
        day = start + timedelta(days=i)
        if day.weekday() < 5:
            schedule[day] = ROTATION[shift % len(ROTATION)]
            shift += 1
    print("shifts", len(schedule), "days", len(ROTATION))
    for offset in range(14):
        key = start + timedelta(days=offset)
        who = schedule.get(key)
        if who is None:
            print(key.isoformat(), key.strftime("%a"), "closed")
        else:
            print(key.isoformat(), key.strftime("%a"), who)
    monday = date(2024, 4, 1)
    friday = date(2024, 4, 5)
    print(schedule[monday], schedule[friday], schedule.get(date(2024, 4, 6), "none"))
    later = friday + timedelta(days=3)
    print(later in schedule, monday in schedule, later - monday)


main()
