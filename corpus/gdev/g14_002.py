# task: Use dataclasses.asdict to convert a nested dataclass Order containing a list of LineItem objects into a dictionary and print it.
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal


@dataclass
class LineItem:
    sku: str
    description: str
    quantity: int
    unit_price: Decimal

    def total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Order:
    order_id: int
    customer: str
    items: list[LineItem] = field(default_factory=list)

    def grand_total(self) -> Decimal:
        return sum((item.total() for item in self.items), Decimal("0.00"))


def build_order() -> Order:
    return Order(
        order_id=1001,
        customer="Alice Example",
        items=[
            LineItem(sku="A-100", description="Widget", quantity=3,
                     unit_price=Decimal("2.50")),
            LineItem(sku="B-200", description="Gadget", quantity=1,
                     unit_price=Decimal("19.99")),
            LineItem(sku="C-300", description="Doohickey", quantity=2,
                     unit_price=Decimal("7.25")),
        ],
    )


def main() -> None:
    order = build_order()
    data = asdict(order)
    print(data)
    print(json.dumps(data, default=str, indent=2))
    print("Grand total:", order.grand_total())


if __name__ == "__main__":
    main()
