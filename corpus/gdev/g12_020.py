# task: Simulate a periodic review inventory policy with an order-up-to level, then print the average on-hand stock over the simulation.
import random
from collections import defaultdict


def simulate_periodic_review(
    horizon: int,
    review_period: int,
    order_up_to: int,
    lead_time: int,
    max_demand: int,
) -> float:
    """Simulate a periodic review order-up-to policy with lost sales.

    Each day:
      1. Scheduled deliveries arrive.
      2. Random demand occurs; unmet demand is lost.
      3. On review days, the inventory position is raised to order_up_to.
      4. End-of-day on-hand stock is recorded.

    Returns the average end-of-day on-hand stock over the horizon.
    """
    on_hand: int = order_up_to
    on_order: int = 0
    arrivals: defaultdict[int, int] = defaultdict(int)
    total_on_hand: int = 0

    for day in range(horizon):
        # 1. Receive deliveries due today.
        received = arrivals.pop(day, 0)
        on_hand += received
        on_order -= received

        # 2. Demand (lost sales if stock runs out).
        demand = random.randint(0, max_demand)
        sold = min(on_hand, demand)
        on_hand -= sold

        # 3. Periodic review and order placement.
        if day % review_period == 0:
            inventory_position = on_hand + on_order
            order_qty = max(0, order_up_to - inventory_position)
            if order_qty > 0:
                arrivals[day + lead_time] += order_qty
                on_order += order_qty

        # 4. Record end-of-day on-hand stock.
        total_on_hand += on_hand

    return total_on_hand / horizon


def main() -> None:
    random.seed(20240601)

    horizon: int = 365
    review_period: int = 7
    order_up_to: int = 60
    lead_time: int = 2
    max_demand: int = 10

    average_on_hand: float = simulate_periodic_review(
        horizon=horizon,
        review_period=review_period,
        order_up_to=order_up_to,
        lead_time=lead_time,
        max_demand=max_demand,
    )

    print(f"Simulation horizon (days): {horizon}")
    print(f"Review period (days): {review_period}")
    print(f"Order-up-to level: {order_up_to}")
    print(f"Lead time (days): {lead_time}")
    print(f"Average on-hand stock: {average_on_hand:.2f}")


if __name__ == "__main__":
    main()
