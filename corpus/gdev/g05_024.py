# task: Build a nested dictionary of sales totals by region and quarter from fixed records and print the total for each region.
from collections import defaultdict
from typing import Dict, List, Tuple


SalesRecord = Tuple[str, str, float]  # (region, quarter, amount)

RECORDS: List[SalesRecord] = [
    ("North", "Q1", 12000.50),
    ("North", "Q2", 15000.00),
    ("North", "Q3", 9800.25),
    ("North", "Q4", 17650.75),
    ("South", "Q1", 8700.00),
    ("South", "Q2", 11200.40),
    ("South", "Q3", 13050.00),
    ("South", "Q4", 10999.99),
    ("East", "Q1", 7600.10),
    ("East", "Q2", 9100.60),
    ("East", "Q3", 8800.00),
    ("East", "Q4", 12400.25),
    ("West", "Q1", 14250.00),
    ("West", "Q2", 13980.75),
    ("West", "Q3", 15500.50),
    ("West", "Q4", 16025.00),
    ("North", "Q2", 2500.00),
    ("West", "Q1", 1000.00),
]


def build_sales_table(records: List[SalesRecord]) -> Dict[str, Dict[str, float]]:
    """Aggregate sales amounts into a nested dict: region -> quarter -> total."""
    table: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for region, quarter, amount in records:
        table[region][quarter] += amount
    # Convert to plain dicts with sorted keys for deterministic structure.
    return {
        region: dict(sorted(quarters.items()))
        for region, quarters in sorted(table.items())
    }


def region_totals(table: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """Sum each region's quarterly totals."""
    return {
        region: sum(quarters.values())
        for region, quarters in table.items()
    }


def main() -> None:
    table = build_sales_table(RECORDS)
    totals = region_totals(table)

    print("Sales totals by region and quarter:")
    for region, quarters in table.items():
        print(f"{region}:")
        for quarter, amount in quarters.items():
            print(f"  {quarter}: {amount:,.2f}")

    print()
    print("Total per region:")
    for region, total in totals.items():
        print(f"{region}: {total:,.2f}")


if __name__ == "__main__":
    main()
