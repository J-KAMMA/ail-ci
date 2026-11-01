# task: Simulate a seeded single-server queue and verify Little's Law by printing the arrival rate, the average time in system, and the average number in system.
import random
from typing import List, Tuple


def generate_customers(
    rng: random.Random, n_customers: int, arrival_rate: float, service_rate: float
) -> Tuple[List[float], List[float]]:
    """Generate Poisson arrival times and exponential service times."""
    arrivals: List[float] = []
    services: List[float] = []
    t = 0.0
    for _ in range(n_customers):
        t += rng.expovariate(arrival_rate)
        arrivals.append(t)
        services.append(rng.expovariate(service_rate))
    # Pair arrivals and services in a list so the FIFO pass below can use both.
    return arrivals, services


def run_fifo_server(arrivals: List[float], services: List[float]) -> List[float]:
    """Return the departure time of each customer in a single FIFO server."""
    departures: List[float] = []
    server_free_at = 0.0
    for arr, svc in zip(arrivals, services):
        start = max(arr, server_free_at)
        dep = start + svc
        departures.append(dep)
        server_free_at = dep
    return departures


def time_average_number_in_system(
    arrivals: List[float], departures: List[float]
) -> Tuple[float, float]:
    """
    Integrate the number-in-system process N(t) over [0, T], where T is the
    time of the final departure (when the system empties).
    Returns (area, T).
    """
    events: List[Tuple[float, int]] = []
    for a in arrivals:
        events.append((a, +1))
    for d in departures:
        events.append((d, -1))
    events.sort(key=lambda e: e[0])

    area = 0.0
    n_in_system = 0
    prev_t = 0.0
    for t, delta in events:
        area += n_in_system * (t - prev_t)
        n_in_system += delta
        prev_t = t
    return area, prev_t


def main() -> None:
    seed = 12345
    n_customers = 200_000
    arrival_rate = 0.8
    service_rate = 1.0

    rng = random.Random(seed)
    random.seed(seed)  # Seed the module-level generator too, for full determinism.

    arrivals, services = generate_customers(rng, n_customers, arrival_rate, service_rate)
    departures = run_fifo_server(arrivals, services)

    sojourn_times = [d - a for a, d in zip(arrivals, departures)]
    total_time_in_system = sum(sojourn_times)

    area, horizon = time_average_number_in_system(arrivals, departures)

    lam_hat = n_customers / horizon          # observed arrival rate
    w_hat = total_time_in_system / n_customers  # average time in system
    l_hat = area / horizon                   # time-average number in system

    little_rhs = lam_hat * w_hat
    rel_err = abs(l_hat - little_rhs) / little_rhs

    rho = arrival_rate / service_rate
    w_theory = 1.0 / (service_rate - arrival_rate)
    l_theory = rho / (1.0 - rho)

    print("Single-server FIFO queue simulation (M/M/1-style)")
    print(f"Seed: {seed}")
    print(f"Customers: {n_customers}")
    print(f"Target arrival rate: {arrival_rate:.6f}")
    print(f"Service rate: {service_rate:.6f}")
    print()
    print(f"Arrival rate (lambda):          {lam_hat:.6f}")
    print(f"Average time in system (W):     {w_hat:.6f}")
    print(f"Average number in system (L):   {l_hat:.6f}")
    print()
    print(f"Little's Law check: L = lambda * W")
    print(f"  lambda * W = {little_rhs:.6f}")
    print(f"  L          = {l_hat:.6f}")
    print(f"  relative error = {rel_err:.2e}")
    print()
    print("Theoretical M/M/1 values for comparison:")
    print(f"  W = 1/(mu - lambda) = {w_theory:.6f}")
    print(f"  L = rho/(1 - rho)   = {l_theory:.6f}")


if __name__ == "__main__":
    main()
