# task: Simulate a small bank as a discrete-event system using a heap-based event queue, then print the events in the order they were processed.
from __future__ import annotations

import heapq
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto


class EventKind(Enum):
    ARRIVAL = auto()
    DEPARTURE = auto()


@dataclass(order=True)
class Event:
    """A scheduled event. Ordering uses (time, seq) so ties are broken deterministically."""

    time: float
    seq: int
    kind: EventKind = field(compare=False)
    customer_id: int = field(compare=False)
    teller_id: int = field(compare=False, default=-1)


@dataclass
class Customer:
    customer_id: int
    arrival_time: float
    service_time: float
    start_time: float | None = None
    finish_time: float | None = None

    @property
    def wait_time(self) -> float:
        if self.start_time is None:
            raise ValueError(f"customer {self.customer_id} was never served")
        return self.start_time - self.arrival_time


class BankSimulation:
    """Discrete-event simulation of a bank with several tellers and one FIFO queue."""

    def __init__(self, num_tellers: int, num_customers: int, seed: int) -> None:
        self.rng = random.Random(seed)
        self.clock: float = 0.0
        self.events: list[Event] = []
        self.seq: int = 0
        self.waiting: deque[Customer] = deque()
        self.free_tellers: list[int] = list(range(num_tellers))
        heapq.heapify(self.free_tellers)
        self.customers: dict[int, Customer] = {}
        self.completed: list[Customer] = []
        self.max_queue_length: int = 0
        self.log: list[str] = []

        arrival_time = 0.0
        for cid in range(num_customers):
            arrival_time += self.rng.expovariate(1 / 2.0)
            service_time = self.rng.uniform(1.0, 4.0)
            self.customers[cid] = Customer(cid, arrival_time, service_time)
            self._schedule(arrival_time, EventKind.ARRIVAL, cid)

    def _schedule(self, time: float, kind: EventKind, customer_id: int, teller_id: int = -1) -> None:
        heapq.heappush(self.events, Event(time, self.seq, kind, customer_id, teller_id))
        self.seq += 1

    def _emit(self, message: str) -> None:
        self.log.append(f"t={self.clock:8.3f}  {message}")

    def run(self) -> list[str]:
        while self.events:
            event = heapq.heappop(self.events)
            self.clock = event.time
            if event.kind is EventKind.ARRIVAL:
                self._on_arrival(event)
            else:
                self._on_departure(event)
        return self.log

    def _on_arrival(self, event: Event) -> None:
        customer = self.customers[event.customer_id]
        self._emit(f"ARRIVAL    customer={customer.customer_id}")
        if self.free_tellers:
            teller_id = heapq.heappop(self.free_tellers)
            self._start_service(customer, teller_id)
        else:
            self.waiting.append(customer)
            self.max_queue_length = max(self.max_queue_length, len(self.waiting))
            self._emit(f"QUEUED     customer={customer.customer_id} queue_length={len(self.waiting)}")

    def _start_service(self, customer: Customer, teller_id: int) -> None:
        customer.start_time = self.clock
        finish = self.clock + customer.service_time
        self._schedule(finish, EventKind.DEPARTURE, customer.customer_id, teller_id)
        self._emit(
            f"SERVE      customer={customer.customer_id} teller={teller_id} "
            f"wait={customer.wait_time:.3f} service={customer.service_time:.3f}"
        )

    def _on_departure(self, event: Event) -> None:
        customer = self.customers[event.customer_id]
        customer.finish_time = self.clock
        self.completed.append(customer)
        self._emit(f"DEPARTURE  customer={customer.customer_id} teller={event.teller_id}")

        if self.waiting:
            next_customer = self.waiting.popleft()
            self._start_service(next_customer, event.teller_id)
        else:
            heapq.heappush(self.free_tellers, event.teller_id)
            self._emit(f"TELLER     teller={event.teller_id} now idle")

    def summary(self) -> list[str]:
        total_wait = sum(c.wait_time for c in self.completed)
        avg_wait = total_wait / len(self.completed) if self.completed else 0.0
        last_finish = max((c.finish_time for c in self.completed if c.finish_time is not None),
                          default=0.0)
        return [
            "",
            "Summary",
            f"  customers served : {len(self.completed)}",
            f"  average wait     : {avg_wait:.3f}",
            f"  max queue length : {self.max_queue_length}",
            f"  last departure   : {last_finish:.3f}",
        ]


def main() -> None:
    random.seed(42)
    sim = BankSimulation(num_tellers=2, num_customers=12, seed=42)
    for line in sim.run():
        print(line)
    for line in sim.summary():
        print(line)


if __name__ == "__main__":
    main()
