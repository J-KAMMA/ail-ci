# task: Calculate the number of seconds elapsed between the fixed start 1999-12-31 23:59:59 and the fixed end 2000-01-01 00:00:01.
from datetime import datetime


def main() -> None:
    start: datetime = datetime(1999, 12, 31, 23, 59, 59)
    end: datetime = datetime(2000, 1, 1, 0, 0, 1)
    elapsed: float = (end - start).total_seconds()
    print(int(elapsed))


if __name__ == "__main__":
    main()
