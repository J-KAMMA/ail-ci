# task: Simulate a gas station with two pumps and seeded car arrivals, then print the average time cars wait before reaching a pump.
import heapq
import random
from dataclasses import dataclass


SEED = 20240601
NUM_CARS = 1000
NUM_PUMPS = 2
MEAN_INTERARRIVAL_MIN = 3.0
MIN_SERVICE_MIN = 2.0
MAX_SERVICE_MIN = 6.0


@dataclass(frozen=True)
class Car:
    arrival: float
    service: float


def generate_cars(count: int, seed: int) -> list[Car]:
    """Create a deterministic sequence of cars with arrival and service times."""
    rng = random.Random(seed)
    cars: list[Car] = []
    clock = 0.0
    for _ in range(count):
        clock += rng.expovariate(1.0 / MEAN_INTERARRIVAL_MIN)
        service = rng.uniform(MIN_SERVICE_MIN, MAX_SERVICE_MIN)
        cars.append(Car(arrival=clock, service=service))
    return cars


def simulate(cars: list[Car], num_pumps: int) -> list[float]:
    """
    Serve cars first-come, first-served at the first pump that becomes free.
    Returns the waiting time (before reaching a pump) for each car.
    """
    # Heap of times at which each pump becomes free.
    free_times: list[float] = [0.0] * num_pumps
    heapq.heapify(free_times)

    waits: list[float] = []
    for car in cars:
        earliest_free = heapq.heappop(free_times)
        start = max(car.arrival, earliest_free)
        waits.append(start - car.arrival)
        heapq.heappush(free_times, start + car.service)
    return waits


def main() -> None:
    cars = generate_cars(NUM_CARS, SEED)
    waits = simulate(cars, NUM_PUMPS)
    average_wait = sum(waits) / len(waits)
    print(f"Cars served: {len(cars)}")
    print(f"Pumps: {NUM_PUMPS}")
    print(f"Average wait before reaching a pump: {average_wait:.2f} minutes")


if __name__ == "__main__":
    main()
