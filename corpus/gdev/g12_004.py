# task: Simulate a bank queue where VIP customers are always served before regular customers, then print the order in which customers were served.
from __future__ import annotations

import heapq
from dataclasses import dataclass


@dataclass(frozen=True)
class Customer:
    name: str
    is_vip: bool
    arrival: int  # minute the customer enters the queue
    service: int  # minutes needed at the teller


def build_customers() -> list[Customer]:
    """Return a fixed, deterministic list of bank customers."""
    return [
        Customer("Alice", False, 0, 4),
        Customer("Bob", False, 1, 3),
        Customer("Carol", True, 2, 5),
        Customer("Dave", False, 3, 2),
        Customer("Erin", True, 4, 3),
        Customer("Frank", False, 5, 6),
        Customer("Grace", False, 6, 2),
        Customer("Heidi", True, 9, 4),
        Customer("Ivan", False, 10, 3),
        Customer("Judy", True, 11, 2),
        Customer("Mallory", False, 14, 5),
        Customer("Niaj", True, 15, 3),
    ]


def simulate(customers: list[Customer]) -> list[tuple[Customer, int]]:
    """
    Serve customers one at a time. VIP customers are always chosen before
    regular customers; within each class, first-come first-served.
    Returns a list of (customer, start_minute) in service order.
    """
    pending = sorted(customers, key=lambda c: (c.arrival, c.name))
    waiting: list[tuple[int, int, int, Customer]] = []
    served: list[tuple[Customer, int]] = []

    clock = 0
    next_index = 0
    seq = 0  # unique tiebreaker so Customer objects are never compared

    while next_index < len(pending) or waiting:
        # If nobody is waiting, jump the clock to the next arrival.
        if not waiting and pending[next_index].arrival > clock:
            clock = pending[next_index].arrival

        # Admit everyone who has arrived by now.
        while next_index < len(pending) and pending[next_index].arrival <= clock:
            customer = pending[next_index]
            priority = 0 if customer.is_vip else 1
            heapq.heappush(waiting, (priority, customer.arrival, seq, customer))
            seq += 1
            next_index += 1

        if waiting:
            _, _, _, customer = heapq.heappop(waiting)
            served.append((customer, clock))
            clock += customer.service

    return served


def main() -> None:
    customers = build_customers()
    served = simulate(customers)

    print("Service order (VIP customers are served first):")
    for position, (customer, start) in enumerate(served, start=1):
        tag = "VIP" if customer.is_vip else "Regular"
        print(
            f"{position:>2}. {customer.name:<8} [{tag:<7}] "
            f"arrived at minute {customer.arrival:>2}, served at minute {start:>2}"
        )


if __name__ == "__main__":
    main()
