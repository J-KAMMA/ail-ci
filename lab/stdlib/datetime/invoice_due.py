from datetime import date, timedelta

NET_DAYS = 30


def adjust(d: date) -> date:
    if d.weekday() == 5:
        return d + timedelta(days=2)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def due(invoice: str, issued: str) -> None:
    try:
        start = date.fromisoformat(issued)
    except ValueError as e:
        print(invoice, "bad date:", type(e).__name__, e)
        return
    end = adjust(start + timedelta(days=NET_DAYS))
    print(invoice, start.isoformat(), end.isoformat(), end.strftime("%a %d %b %Y"),
          (end - start).days, end > start)


def main() -> None:
    due("INV-1", "2024-01-01")
    due("INV-2", "2024-02-28")
    due("INV-3", "2024-13-01")
    due("INV-4", "2023-12-29")
    due("INV-5", "2024-02-30")
    due("INV-6", "2024-06-15")


main()
