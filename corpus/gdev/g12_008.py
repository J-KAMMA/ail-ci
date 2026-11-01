# task: Simulate an M/M/1 queue using seeded exponential interarrival and service times, then print the time-averaged number of customers in the system.
import random
from math import inf


def simulate_mm1(arrival_rate: float, service_rate: float, num_customers: int) -> tuple[float, float]:
    """Simulate an M/M/1 FIFO queue and return (time-averaged number in system, total simulated time)."""
    t: float = 0.0
    n: int = 0
    area: float = 0.0
    arrived: int = 0
    served: int = 0

    next_arrival: float = random.expovariate(arrival_rate)
    next_departure: float = inf

    while served < num_customers:
        if next_arrival <= next_departure:
            # Arrival event
            area += n * (next_arrival - t)
            t = next_arrival
            n += 1
            arrived += 1
            if arrived < num_customers:
                next_arrival = t + random.expovariate(arrival_rate)
            else:
                next_arrival = inf
            if n == 1:
                next_departure = t + random.expovariate(service_rate)
        else:
            # Departure event
            area += n * (next_departure - t)
            t = next_departure
            n -= 1
            served += 1
            if n > 0:
                next_departure = t + random.expovariate(service_rate)
            else:
                next_departure = inf

    average_n: float = area / t
    return average_n, t


def main() -> None:
    random.seed(12345)

    arrival_rate: float = 0.8
    service_rate: float = 1.0
    num_customers: int = 200_000

    avg_n, total_time = simulate_mm1(arrival_rate, service_rate, num_customers)

    rho: float = arrival_rate / service_rate
    theoretical: float = rho / (1.0 - rho)

    print("M/M/1 queue simulation")
    print(f"Arrival rate (lambda): {arrival_rate:.4f}")
    print(f"Service rate (mu):     {service_rate:.4f}")
    print(f"Customers simulated:   {num_customers}")
    print(f"Simulated time:        {total_time:.4f}")
    print(f"Time-averaged number in system: {avg_n:.4f}")
    print(f"Theoretical value (rho/(1-rho)): {theoretical:.4f}")


if __name__ == "__main__":
    main()
