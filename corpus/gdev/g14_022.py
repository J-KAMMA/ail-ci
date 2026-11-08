# task: Group a list of dataclass Transaction records by category using itertools.groupby after sorting and print totals.
from dataclasses import dataclass
from itertools import groupby
from operator import attrgetter


@dataclass(frozen=True)
class Transaction:
    transaction_id: int
    category: str
    description: str
    amount_cents: int


def build_transactions() -> list[Transaction]:
    """Return a fixed, deterministic list of transactions (no input is read)."""
    return [
        Transaction(1, "groceries", "Weekly market", 8452),
        Transaction(2, "utilities", "Electric bill", 12300),
        Transaction(3, "dining", "Pizza night", 3675),
        Transaction(4, "groceries", "Bakery run", 1299),
        Transaction(5, "transport", "Monthly pass", 9500),
        Transaction(6, "dining", "Lunch with team", 4820),
        Transaction(7, "utilities", "Water bill", 4510),
        Transaction(8, "transport", "Taxi to airport", 3390),
        Transaction(9, "groceries", "Pharmacy items", 2875),
        Transaction(10, "entertainment", "Movie tickets", 2400),
        Transaction(11, "dining", "Coffee shop", 615),
        Transaction(12, "entertainment", "Concert", 8900),
    ]


def format_cents(cents: int) -> str:
    """Format an integer amount of cents as dollars with two decimals."""
    sign = "-" if cents < 0 else ""
    dollars, remainder = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{remainder:02d}"


def main() -> None:
    transactions = build_transactions()

    # groupby requires input sorted by the grouping key.
    # Sorting by (category, transaction_id) also makes ordering within groups stable.
    sorted_txns = sorted(transactions, key=lambda t: (t.category, t.transaction_id))

    grand_total = 0
    for category, group in groupby(sorted_txns, key=attrgetter("category")):
        items = list(group)
        total = sum(t.amount_cents for t in items)
        grand_total += total

        print(f"Category: {category}")
        for txn in items:
            print(f"  #{txn.transaction_id:>3}  {txn.description:<20} {format_cents(txn.amount_cents):>12}")
        print(f"  Subtotal ({len(items)} items): {format_cents(total)}")
        print()

    print(f"Grand total: {format_cents(grand_total)}")


if __name__ == "__main__":
    main()
