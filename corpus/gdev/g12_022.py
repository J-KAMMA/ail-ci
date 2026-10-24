# task: Simulate a newsvendor problem over 30 days with seeded random demand for several order quantities, then print the most profitable quantity.
import random
from dataclasses import dataclass

SEED: int = 20240601
NUM_DAYS: int = 30
MEAN_DEMAND: float = 50.0
STD_DEMAND: float = 12.0
CANDIDATE_QUANTITIES: tuple[int, ...] = tuple(range(30, 81, 5))


@dataclass(frozen=True)
class Economics:
    price: float = 10.0      # selling price per unit
    cost: float = 6.0        # purchase cost per unit
    salvage: float = 2.0     # salvage value per unperturbed leftover unit


def generate_demands(num_days: int, mean: float, std: float) -> list[int]:
    """Generate a deterministic sequence of non-negative integer daily demands."""
    random.seed(SEED)
    demands: list[int] = []
    for _ in range(num_days):
        raw = random.gauss(mean, std)
        demands.append(max(0, round(raw)))
    return demands


def daily_profit(order_qty: int, demand: int, econ: Economics) -> float:
    """Profit for one day given an order quantity and realized demand."""
    sold = min(order_qty, demand)
    leftover = order_qty - sold
    revenue = sold * econ.price
    salvage_revenue = leftover * econ.salvage
    purchase_cost = order_qty * econ.cost
    return revenue + salvage_revenue - purchase_cost


def simulate_quantity(order_qty: int, demands: list[int], econ: Economics) -> float:
    """Total profit over all simulated days for a fixed order quantity."""
    return sum(daily_profit(order_qty, d, econ) for d in demands)


def main() -> None:
    econ = Economics()
    demands = generate_demands(NUM_DAYS, MEAN_DEMAND, STD_DEMAND)

    print(f"Newsvendor simulation over {NUM_DAYS} days (seed={SEED})")
    print(f"Price={econ.price:.2f}, Cost={econ.cost:.2f}, Salvage={econ.salvage:.2f}")
    print(f"Mean demand total: {sum(demands) / NUM_DAYS:.2f}")
    print()
    print(f"{'Quantity':>8} {'Total Profit':>14} {'Avg/Day':>10}")

    results: dict[int, float] = {}
    for qty in CANDIDATE_QUANTITIES:
        total = simulate_quantity(qty, demands, econ)
        results[qty] = total
        print(f"{qty:>8} {total:>14.2f} {total / NUM_DAYS:>10.2f}")

    best_qty = max(CANDIDATE_QUANTITIES, key=lambda q: results[q])
    print()
    print(f"Most profitable order quantity: {best_qty} "
          f"(total profit {results[best_qty]:.2f})")


if __name__ == "__main__":
    main()
