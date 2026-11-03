# task: Simulate a car wash with a single bay and fixed service time per car, then print the total revenue earned.
import random
from dataclasses import dataclass, field


SERVICE_TIME_MIN: int = 5          # fixed service time per car, in minutes
PRICE_CENTS: int = 1000            # price per wash, in cents
MAX_CARS_IN_SYSTEM: int = 4        # one car in the bay plus up to three waiting
SIM_END_MIN: int = 480             # simulate an 8-hour day
RANDOM_SEED: int = 2024


@dataclass
class CarWashStats:
    arrivals: int = 0
    served: int = 0
    balked: int = 0
    revenue_cents: int = 0
    total_wait_min: int = 0
    max_wait_min: int = 0
    finish_times: list[int] = field(default_factory=list)


def generate_arrivals(rng: random.Random, end_time: int) -> list[int]:
    """Generate car arrival times (in minutes) using random gaps of 1 to 8 minutes."""
    arrivals: list[int] = []
    t = 0
    while True:
        t += rng.randint(1, 8)
        if t >= end_time:
            break
        arrivals.append(t)
    return arrivals


def simulate(arrivals: list[int]) -> CarWashStats:
    """Run a single-bay FIFO car wash with a limited number of cars allowed in the system."""
    stats = CarWashStats()
    bay_free_at = 0

    for arrival in arrivals:
        stats.arrivals += 1

        # Cars still present (in the bay or waiting) at the moment of arrival.
        in_system = sum(1 for finish in stats.finish_times if finish > arrival)
        if in_system >= MAX_CARS_IN_SYSTEM:
            stats.balked += 1
            continue

        start = max(arrival, bay_free_at)
        finish = start + SERVICE_TIME_MIN
        bay_free_at = finish

        wait = start - arrival
        stats.total_wait_min += wait
        stats.max_wait_min = max(stats.max_wait_min, wait)

        stats.finish_times.append(finish)
        stats.served += 1
        stats.revenue_cents += PRICE_CENTS

    return stats


def format_cents(cents: int) -> str:
    dollars, remainder = divmod(cents, 100)
    return f"${dollars:,}.{remainder:02d}"


def main() -> None:
    rng = random.Random(RANDOM_SEED)
    random.seed(RANDOM_SEED)  # seed the global RNG too, for completeness

    arrivals = generate_arrivals(rng, SIM_END_MIN)
    stats = simulate(arrivals)

    avg_wait = stats.total_wait_min / stats.served if stats.served else 0.0

    print("Car Wash Simulation")
    print("-------------------")
    print(f"Simulated period:      {SIM_END_MIN} minutes")
    print(f"Service time per car:  {SERVICE_TIME_MIN} minutes")
    print(f"Price per wash:        {format_cents(PRICE_CENTS)}")
    print(f"Max cars in system:    {MAX_CARS_IN_SYSTEM}")
    print()
    print(f"Cars arrived:          {stats.arrivals}")
    print(f"Cars served:           {stats.served}")
    print(f"Cars balked:           {stats.balked}")
    print(f"Average wait (min):    {avg_wait:.2f}")
    print(f"Maximum wait (min):    {stats.max_wait_min}")
    print()
    print(f"Total revenue:         {format_cents(stats.revenue_cents)}")


if __name__ == "__main__":
    main()
