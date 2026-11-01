from datetime import date, datetime, time, timedelta


def entry(day: date, start: time, end: time) -> tuple[datetime, datetime, timedelta]:
    began = datetime.combine(day, start)
    finished = datetime.combine(day, end)
    if finished < began:
        finished = finished + timedelta(days=1)
    return began, finished, finished - began


def main() -> None:
    day = date(2024, 6, 3)
    shifts = [
        ("monday", time(9, 0), time(17, 30)),
        ("tuesday", time(8, 45, 15), time(18, 0)),
        ("night", time(22, 0), time(6, 30)),
    ]
    total = timedelta()
    for name, start, end in shifts:
        began, finished, length = entry(day, start, end)
        total += length
        print(name, began.strftime("%Y-%m-%d %H:%M:%S"), finished.isoformat(" "),
              length, length.total_seconds(), finished.date() - began.date())
    print("total", total, total.total_seconds() / 3600)
    moment = datetime(2024, 6, 3, 17, 30)
    print(moment.time(), moment.date(), moment.replace(hour=9, minute=15).isoformat())
    print(moment.hour, moment.minute, moment.second, moment.microsecond)
    print(datetime.combine(day, time(12, 0)) - datetime.combine(day, time(9, 0)))
    print(time(23, 59, 59, 999999).isoformat(), time(7, 5).isoformat(timespec="minutes"))


main()
