# task: Group embedded CSV rows by a category column and print the sum of another numeric column for each group.
import csv
import io
from collections import defaultdict
from decimal import Decimal, InvalidOperation

EMBEDDED_CSV = """\
category,item,amount
fruit,apple,1.50
vegetable,carrot,0.75
fruit,banana,2.25
dairy,milk,3.00
vegetable,potato,1.10
fruit,cherry,4.40
dairy,cheese,5.25
grain,rice,2.00
vegetable,onion,0.60
grain,bread,3.10
dairy,yogurt,1.80
"""


def sum_by_category(csv_text: str, category_col: str, value_col: str) -> dict[str, Decimal]:
    """Return a mapping of category -> sum of numeric values, preserving first-seen order."""
    totals: dict[str, Decimal] = defaultdict(Decimal)
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        category = (row.get(category_col) or "").strip()
        raw_value = (row.get(value_col) or "").strip()
        try:
            value = Decimal(raw_value)
        except InvalidOperation:
            continue  # skip rows with non-numeric values
        totals[category] += value
    return dict(totals)


def main() -> None:
    totals = sum_by_category(EMBEDDED_CSV, "category", "amount")
    for category in sorted(totals):
        print(f"{category}: {totals[category]:.2f}")


if __name__ == "__main__":
    main()
