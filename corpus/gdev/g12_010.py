# task: Simulate a bounded waiting room with capacity 10 where arrivals are turned away when full, then print the total number of rejected arrivals.
import random
from collections import deque

CAPACITY: int = 10
SIMULATION_STEPS: int = 1000
ARRIVAL_PROBABILITY: float = 0.6
SERVICE_PROBABILITY: float = 0.5
RANDOM_SEED: int = 42


def simulate_waiting_room(steps: int, capacity: int) -> int:
    """Run the bounded waiting room simulation and return rejected arrivals."""
    waiting: deque[int] = deque()
    rejected: int = 0
    next_customer_id: int = 0

    for _ in range(steps):
        # Possible arrival this time step.
        if random.random() < ARRIVAL_PROBABILITY:
            if len(waiting) >= capacity:
                rejected += 1
            else:
                waiting.append(next_customer_id)
            next_customer_id += 1

        # Possible service completion this time step.
        if waiting and random.random() < SERVICE_PROBABILITY:
            waiting.popleft()

    return rejected


def main() -> None:
    random.seed(RANDOM_SEED)
    rejected_total: int = simulate_waiting_room(SIMULATION_STEPS, CAPACITY)
    print(f"Total rejected arrivals: {rejected_total}")


if __name__ == "__main__":
    main()
