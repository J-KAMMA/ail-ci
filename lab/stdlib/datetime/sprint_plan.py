from datetime import date, timedelta

SPRINTS = 6
LENGTH = 14


def main() -> None:
    start = date(2024, 1, 1)
    for i in range(SPRINTS):
        first = start + timedelta(weeks=i * 2)
        last = first + timedelta(days=LENGTH - 1)
        review = last + timedelta(days=1)
        if review.weekday() >= 5:
            review = review + timedelta(days=7 - review.weekday())
        print(i + 1, first.isoformat(), last.isoformat(), review.isoformat(),
              first.strftime("%a %d %b %Y"), last.strftime("%j %G-W%V-%u"),
              first.weekday(), last.isoweekday())
    print("total days", (start + timedelta(weeks=SPRINTS * 2) - start).days)
    print("first ordinal", start.toordinal(), "last ordinal",
          (start + timedelta(weeks=SPRINTS * 2 - 1)).toordinal())


main()
