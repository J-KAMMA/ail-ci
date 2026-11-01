# task: Simulate a (s, S) inventory policy over 60 days with seeded random daily demand, then print the number of days with a stockout.
import random


def run_simulation(
    num_days: int = 60,
    s: int = 20,
    big_s: int = 50,
    lead_time: int = 2,
    max_demand: int = 15,
    seed: int = 42,
) -> int:
    """Simulate a daily (s, S) inventory policy and count stockout days.

    Each day:
      1. Receive any orders arriving today.
      2. Observe demand; if demand exceeds on-hand stock, record a stockout
         (lost sales) and empty the shelf; otherwise subtract demand.
      3. Review inventory position (on-hand + on-order). If it is at or below s,
         order up to big_s, arriving after lead_time days.
    """
    rng = random.Random(seed)
    random.seed(seed)  # Ensure global RNG is also deterministic if used elsewhere.

    on_hand: int = big_s
    # Pipeline of outstanding orders as (arrival_day, quantity) pairs.
    pipeline: list[tuple[int, int]] = []
    stockout_days: int = 0

    for day in range(num_days):
        # 1. Receive arrivals scheduled for today.
        arrived = sum(qty for arrival, qty in pipeline if arrival == day)
        pipeline = [(arrival, qty) for arrival, qty in pipeline if arrival > day]
        on_hand += arrived

        # 2. Serve demand.
        demand = rng.randint(0, max_demand)
        if demand > on_hand:
            stockout_days += 1
            on_hand = 0
        else:
            on_hand -= demand

        # 3. Review and possibly reorder up to S.
        on_order = sum(qty for _, qty in pipeline)
        position = on_hand + on_order
        if position <= s:
            order_qty = big_s - position
            pipeline.append((day + lead_time, order_qty))

    return stockout_days


def main() -> None:
    stockout_days = run_simulation()
    print(f"Days with a stockout (60-day simulation): {stockout_days}")


if __name__ == "__main__":
    main()
