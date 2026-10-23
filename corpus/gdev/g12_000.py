# task: Simulate a single-teller bank where customers arrive at fixed intervals with service times from a fixed list, then print the average wait time.
from dataclasses import dataclass


@dataclass(frozen=True)
class Customer:
    number: int
    arrival_time: int
    service_time: int


@dataclass(frozen=True)
class ServiceRecord:
    customer: Customer
    start_time: int
    wait_time: int
    finish_time: int


ARRIVAL_INTERVAL: int = 4
SERVICE_TIMES: list[int] = [5, 3, 8, 2, 6, 4, 7, 1, 3, 5, 2, 6]


def build_customers(interval: int, service_times: list[int]) -> list[Customer]:
    """Create customers arriving at fixed intervals, starting at time 0."""
    return [
        Customer(number=i + 1, arrival_time=i * interval, service_time=service)
        for i, service in enumerate(service_times)
    ]


def simulate(customers: list[Customer]) -> list[ServiceRecord]:
    """Serve customers in FIFO order with a single teller."""
    records: list[ServiceRecord] = []
    teller_free_at: int = 0
    for customer in customers:
        start_time = max(customer.arrival_time, teller_free_at)
        wait_time = start_time - customer.arrival_time
        finish_time = start_time + customer.service_time
        records.append(
            ServiceRecord(
                customer=customer,
                start_time=start_time,
                wait_time=wait_time,
                finish_time=finish_time,
            )
        )
        teller_free_at = finish_time
    return records


def average_wait(records: list[ServiceRecord]) -> float:
    """Return the mean wait time across all served customers."""
    if not records:
        return 0.0
    total = sum(record.wait_time for record in records)
    return total / len(records)


def main() -> None:
    customers = build_customers(ARRIVAL_INTERVAL, SERVICE_TIMES)
    records = simulate(customers)

    print("Customer  Arrive  Start  Service  Wait  Finish")
    for record in records:
        c = record.customer
        print(
            f"{c.number:>8}  {c.arrival_time:>6}  {record.start_time:>5}  "
            f"{c.service_time:>7}  {record.wait_time:>4}  {record.finish_time:>6}"
        )

    print()
    print(f"Customers served: {len(records)}")
    print(f"Average wait time: {average_wait(records):.2f}")


if __name__ == "__main__":
    main()
