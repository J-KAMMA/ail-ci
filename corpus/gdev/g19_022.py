# task: Compute the date exactly 1000 days after 2000-01-01 and print the result along with its weekday.
import datetime


def main() -> None:
    start: datetime.date = datetime.date(2000, 1, 1)
    result: datetime.date = start + datetime.timedelta(days=1000)
    print(f"{result.isoformat()} {result.strftime('%A')}")


if __name__ == "__main__":
    main()
