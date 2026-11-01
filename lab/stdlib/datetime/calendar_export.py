from datetime import time


def main() -> None:
    opens = time.fromisoformat("09:30:15")
    lunch = time.fromisoformat("12:00")
    closes = time.fromisoformat("17:45:30.123456")
    print(opens, opens.isoformat(), opens.strftime("%H:%M:%S"), opens.hour, opens.minute, opens.second)
    print(lunch.isoformat(timespec="minutes"), lunch.strftime("%I:%M %p"), lunch.minute)
    print(closes.isoformat(timespec="microseconds"), closes.microsecond, closes.strftime("%H:%M:%S.%f"))
    print(opens < lunch, lunch < closes, opens == time(9, 30, 15))
    print(time.fromisoformat("23:59:59.999999"), time.fromisoformat("00:00"))
    for text in ["25:00", "12:60", "noon", "12:00:00+01:00"]:
        try:
            print(text, time.fromisoformat(text))
        except ValueError as e:
            print(text, "invalid", type(e).__name__, e)


main()
