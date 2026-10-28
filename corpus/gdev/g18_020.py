# task: Use defaultdict(int) to total the number of orders per customer from hardcoded order tuples and print the totals sorted by customer name.
from collections import defaultdict


ORDERS: tuple[tuple[str, str], ...] = (
    ("alice", "ord-1001"),
    ("bob", "ord-1002"),
    ("alice", "ord-1003"),
    ("carol", "ord-1004"),
    ("bob", "ord-1005"),
    ("alice", "ord-1006"),
    ("dave", "ord-1007"),
    ("carol", "ord-1008"),
    ("erin", "ord-1009"),
    ("bob", "ord-1010"),
    ("dave", "ord-1011"),
    ("alice", "ord-1012"),
)


def count_orders_per_customer(orders: tuple[tuple[str, str], ...]) -> dict[str, int]:
    totals: defaultdict[str, int] = defaultdict(int)
    for customer, _order_id in orders:
        totals[customer] += 1
    return dict(totals)


def main() -> None:
    totals = count_orders_per_customer(ORDERS)
    for customer in sorted(totals):
        print(f"{customer}: {totals[customer]}")


if __name__ == "__main__":
    main()
