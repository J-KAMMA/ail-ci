from datetime import date, datetime


def main() -> None:
    for stamp in [0, 1700000000, 1700000000.5, 86400, 951782400]:
        local = datetime.fromtimestamp(stamp)
        utc = datetime.utcfromtimestamp(stamp)
        print(stamp, local.isoformat(), utc.isoformat(), local.timetuple().tm_yday,
              utc.timetuple().tm_hour, date.fromtimestamp(stamp))
    day = date(2024, 3, 10)
    tt = day.timetuple()
    print(day.isoformat(), tt.tm_year, tt.tm_mon, tt.tm_mday, tt.tm_wday, tt.tm_yday)
    dt = datetime(2024, 3, 10, 2, 30, 45)
    print(dt.utctimetuple().tm_hour, dt.timetuple().tm_isdst)
    try:
        datetime.fromtimestamp(1e20)
    except (ValueError, OverflowError, OSError) as e:
        print("bad stamp", type(e).__name__)


main()
