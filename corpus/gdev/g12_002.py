# task: Simulate a bank where customers abandon the line if they wait longer than a fixed patience threshold, then print how many customers left.
import heapq
import random


def simulate_bank(
    num_customers: int,
    num_tellers: int,
    mean_interarrival: float,
    mean_service: float,
    patience: float,
) -> tuple[int, int]:
    """Return (customers_served, customers_who_left).

    Customers are processed in arrival order (FIFO). Each customer takes the
    teller that becomes free earliest. If the customer would wait longer than
    the patience threshold, they abandon the line and never occupy a teller.
    """
    teller_free_times: list[float] = [0.0] * num_tellers
    heapq.heapify(teller_free_times)

    arrival_time = 0.0
    served = 0
    left = 0

    for _ in range(num_customers):
        arrival_time += random.expovariate(1.0 / mean_interarrival)
        service_time = random.expovariate(1.0 / mean_service)

        earliest_free = heapq.heappop(teller_free_times)
        start_time = max(arrival_time, earliest_free)
        wait_time = start_time - arrival_time

        if wait_time > patience:
            # Customer abandons the line; the teller stays available.
            left += 1
            heapq.heappush(teller_free_times, earliest_free)
        else:
            served += 1
            heapq.heappush(teller_free_times, start_time + service_time)

    return served, left


def main() -> None:
    random.seed(12345)

    num_customers = 1000
    num_tellers = 3
    mean_interarrival = 1.0
    mean_service = 2.5
    patience = 4.0

    served, left = simulate_bank(
        num_customers=num_customers,
        num_tellers=num_tellers,
        mean_interarrival=mean_interarrival,
        mean_service=mean_service,
        patience=patience,
    )

    print("Bank queue simulation")
    print(f"Tellers: {num_tellers}")
    print(f"Patience threshold: {patience:.1f} time units")
    print(f"Customers arrived: {num_customers}")
    print(f"Customers served: {served}")
    print(f"Customers who left: {left}")


if __name__ == "__main__":
    main()
