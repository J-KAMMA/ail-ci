from datetime import datetime

FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%d %b %Y"]


def parse(text: str) -> None:
    for fmt in FORMATS:
        try:
            when = datetime.strptime(text, fmt)
        except ValueError:
            continue
        print(text, "->", when.strftime("%A %d %B %Y"), when.isoformat(), when.weekday())
        return
    print(text, "-> unparsed")


def main() -> None:
    for text in ["1990-07-04", "04/07/1990", "July 04, 1990", "04 Jul 1990",
                 "1990-02-30", "not a date", "1990-7-4"]:
        parse(text)
    try:
        datetime.strptime("2024-01-01", "%Y/%m/%d")
    except ValueError as e:
        print("mismatch", type(e).__name__, e)
    print(datetime.strptime("2024-01-01", "%Y-%m-%d") - datetime(2023, 12, 25))


main()
