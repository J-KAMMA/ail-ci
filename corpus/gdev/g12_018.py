# task: Simulate a warehouse with a reorder point and a fixed lead time for deliveries, then print the day each replenishment order arrives.
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Order:
    order_id: int
    placed_day: int
    arrival_day: int
    quantity: int


@dataclass
class Warehouse:
    on_hand: int
    reorder_point: int
    order_quantity: int
    lead_time: int
    pending: list[Order] = field(default_factory=list)
    received: list[Order] = field(default_factory=list)
    next_order_id: int = 1
    lost_sales: int = 0

    def in_transit(self) -> int:
        return sum(order.quantity for order in self.pending)

    def receive(self, day: int) -> list[Order]:
        arrived = [order for order in self.pending if order.arrival_day == day]
        self.pending = [order for order in self.pending if order.arrival_day != day]
        for order in arrived:
            self.on_hand += order.quantity
            self.received.append(order)
        return arrived

    def fulfill(self, demand: int) -> None:
        sold = min(demand, self.on_hand)
        self.on_hand -= sold
        self.lost_sales += demand - sold

    def review(self, day: int) -> Order | None:
        position = self.on_hand + self.in_transit()
        if position > self.reorder_point:
            return None
        order = Order(
            order_id=self.next_order_id,
            placed_day=day,
            arrival_day=day + self.lead_time,
            quantity=self.order_quantity,
        )
        self.next_order_id += 1
        self.pending.append(order)
        return order


def generate_demand(days: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    return [rng.randint(0, 12) for _ in range(days)]


def main() -> None:
    random.seed(2024)  # Seeds the global RNG as a safeguard; demand uses its own seeded RNG.

    horizon = 30
    demand = generate_demand(horizon, seed=2024)
    warehouse = Warehouse(
        on_hand=30,
        reorder_point=15,
        order_quantity=40,
        lead_time=3,
    )

    print("Warehouse simulation")
    print(f"Initial on-hand: {warehouse.on_hand}")
    print(f"Reorder point: {warehouse.reorder_point}, order quantity: {warehouse.order_quantity}, "
          f"lead time: {warehouse.lead_time} days")
    print("-" * 60)

    for day in range(1, horizon + 1):
        for order in warehouse.receive(day):
            print(f"Day {day:2d}: order #{order.order_id} arrived "
                  f"(+{order.quantity}, placed day {order.placed_day})")

        daily_demand = demand[day - 1]
        before = warehouse.on_hand
        warehouse.fulfill(daily_demand)
        print(f"Day {day:2d}: demand {daily_demand:2d}, on-hand {before:3d} -> {warehouse.on_hand:3d}")

        placed = warehouse.review(day)
        if placed is not None:
            print(f"Day {day:2d}: placed order #{placed.order_id} "
                  f"(qty {placed.quantity}, expected arrival day {placed.arrival_day})")

    print("-" * 60)
    print("Replenishment arrival summary:")
    if warehouse.received:
        for order in warehouse.received:
            print(f"  order #{order.order_id}: placed day {order.placed_day}, "
                  f"arrived day {order.arrival_day}")
    else:
        print("  no orders arrived")

    if warehouse.pending:
        for order in warehouse.pending:
            print(f"  order #{order.order_id}: still in transit, due day {order.arrival_day}")

    print(f"Total lost sales: {warehouse.lost_sales}")
    print(f"Final on-hand: {warehouse.on_hand}")


if __name__ == "__main__":
    main()
