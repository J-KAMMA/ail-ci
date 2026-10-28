# task: Convert a fixed local time in New York to UTC and to Tokyo time using zoneinfo and print all three times.
from datetime import datetime
from zoneinfo import ZoneInfo


def main() -> None:
    new_york = ZoneInfo("America/New_York")
    tokyo = ZoneInfo("Asia/Tokyo")
    utc = ZoneInfo("UTC")

    # Fixed local time in New York
    local_ny = datetime(2024, 3, 15, 14, 30, 0, tzinfo=new_york)

    # Convert to UTC and Tokyo time
    utc_time = local_ny.astimezone(utc)
    tokyo_time = local_ny.astimezone(tokyo)

    fmt = "%Y-%m-%d %H:%M:%S %Z (UTC%z)"
    print(f"New York: {local_ny.strftime(fmt)}")
    print(f"UTC:      {utc_time.strftime(fmt)}")
    print(f"Tokyo:    {tokyo_time.strftime(fmt)}")


if __name__ == "__main__":
    main()
