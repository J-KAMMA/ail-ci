# task: Build a Inventory base class with a total_value method and a PerishableItem subclass that applies a fixed discount, printing the inventory totals.
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
PERISHABLE_DISCOUNT_RATE = Decimal("0.15")  # fixed 15% discount for perishable stock


@dataclass(frozen=True)
class Item:
    """A single stock line: name, quantity, and unit price."""

    name: str
    quantity: int
    unit_price: Decimal

    def line_value(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(CENT, rounding=ROUND_HALF_UP)


class Inventory:
    """Base inventory holding items and reporting their total value."""

    def __init__(self, name: str, items: list[Item] | None = None) -> None:
        self.name: str = name
        self._items: list[Item] = list(items) if items else []

    @property
    def items(self) -> tuple[Item, ...]:
        return tuple(self._items)

    def add_item(self, item: Item) -> None:
        self._items.append(item)

    def total_value(self) -> Decimal:
        total = sum((item.line_value() for item in self._items), Decimal("0"))
        return Decimal(total).quantize(CENT, rounding=ROUND_HALF_UP)


class PerishableItem(Inventory):
    """Inventory of perishable goods; applies a fixed discount to the total value."""

    def __init__(
        self,
        name: str,
        items: list[Item] | None = None,
        discount_rate: Decimal = PERISHABLE_DISCOUNT_RATE,
    ) -> None:
        super().__init__(name, items)
        self.discount_rate: Decimal = discount_rate

    def discount_amount(self) -> Decimal:
        return (super().total_value() * self.discount_rate).quantize(
            CENT, rounding=ROUND_HALF_UP
        )

    def total_value(self) -> Decimal:
        return super().total_value() - self.discount_amount()


def format_money(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def print_inventory_report(inventory: Inventory) -> None:
    print(f"Inventory: {inventory.name}")
    for item in inventory.items:
        print(
            f"  {item.name:<12} qty={item.quantity:>4}  "
            f"unit={format_money(item.unit_price):>10}  "
            f"line={format_money(item.line_value()):>12}"
        )
    print(f"  Total value: {format_money(inventory.total_value())}")
    if isinstance(inventory, PerishableItem):
        print(
            f"  Discount ({inventory.discount_rate * 100:.0f}%): "
            f"-{format_money(inventory.discount_amount())}"
        )
    print()


def main() -> None:
    general = Inventory(
        "General Goods",
        [
            Item("Hammer", 10, Decimal("12.50")),
            Item("Wrench", 5, Decimal("8.75")),
            Item("Tape", 40, Decimal("2.10")),
        ],
    )

    perishable = PerishableItem(
        "Dairy & Produce",
        [
            Item("Milk", 60, Decimal("1.99")),
            Item("Cheese", 25, Decimal("4.49")),
            Item("Lettuce", 30, Decimal("1.25")),
        ],
    )

    print_inventory_report(general)
    print_inventory_report(perishable)

    combined_total = general.total_value() + perishable.total_value()
    print(f"Combined inventory total: {format_money(combined_total)}")


if __name__ == "__main__":
    main()
