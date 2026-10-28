# task: Parse an embedded CSV string with a header row and print the average of the 'price' column rounded to two decimals.
import csv
import io
from decimal import Decimal, ROUND_HALF_UP


CSV_DATA: str = """\
id,name,price,category
1,Widget,2.50,tools
2,Gadget,10.00,electronics
3,Doohickey,7.25,tools
4,Gizmo,15.99,electronics
5,Thingamajig,3.10,misc
6,Whatsit,12.40,misc
"""


def average_price(text: str) -> float | None:
    """Return the average of the 'price' column, or None if there are no rows."""
    reader = csv.DictReader(io.StringIO(text))
    prices: list[Decimal] = []
    for row in reader:
        raw = (row.get("price") or "").strip()
        if raw:
            prices.append(Decimal(raw))
    if not prices:
        return None
    total = sum(prices, Decimal("0"))
    return float(total / len(prices))


def main() -> None:
    avg = average_price(CSV_DATA)
    if avg is None:
        print("No price data available.")
        return
    rounded = Decimal(str(avg)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    print(f"{rounded:.2f}")


if __name__ == "__main__":
    main()
