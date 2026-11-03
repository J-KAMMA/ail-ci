# task: Simulate a 20-floor building with seeded random passenger requests, then print the average waiting time per request.
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

FLOORS = 20
CAPACITY = 8
NUM_REQUESTS = 300
SEED = 2024


@dataclass(frozen=True)
class Request:
    arrival: int
    origin: int
    destination: int


def generate_requests(rng: random.Random) -> list[Request]:
    """Create a time-ordered list of passenger requests."""
    requests: list[Request] = []
    clock = 0
    for _ in range(NUM_REQUESTS):
        clock += rng.randint(0, 3)
        origin = rng.randrange(FLOORS)
        destination = rng.randrange(FLOORS - 1)
        if destination >= origin:
            destination += 1
        requests.append(Request(clock, origin, destination))
    return requests


def choose_target(
    floor: int,
    riders: list[Request],
    waiting: list[deque[Request]],
) -> int | None:
    """Pick the nearest floor that needs a visit (ties go to the lower floor)."""
    candidates = [r.destination for r in riders]
    if len(riders) < CAPACITY:
        candidates.extend(f for f in range(FLOORS) if waiting[f])
    if not candidates:
        return None
    return min(candidates, key=lambda f: (abs(f - floor), f))


def simulate(requests: list[Request]) -> list[int]:
    """Run a one-elevator simulation and return each request's waiting time in ticks."""
    waiting: list[deque[Request]] = [deque() for _ in range(FLOORS)]
    riders: list[Request] = []
    waits: list[int] = []
    pending: deque[Request] = deque(requests)
    floor = 0
    now = 0

    while pending or riders or any(waiting):
        # Requests arriving at this tick join their floor's queue.
        while pending and pending[0].arrival <= now:
            req = pending.popleft()
            waiting[req.origin].append(req)

        # Riders whose destination is this floor leave.
        riders = [r for r in riders if r.destination != floor]

        # Waiting passengers board while there is room; record their wait.
        while waiting[floor] and len(riders) < CAPACITY:
            req = waiting[floor].popleft()
            waits.append(now - req.arrival)
            riders.append(req)

        # Move one floor toward the next target, if any.
        target = choose_target(floor, riders, waiting)
        if target is not None and target != floor:
            floor += 1 if target > floor else -1

        now += 1

    return waits


def main() -> None:
    rng = random.Random(SEED)
    requests = generate_requests(rng)
    waits = simulate(requests)

    average = sum(waits) / len(waits)
    print(f"Floors: {FLOORS}")
    print(f"Requests served: {len(waits)}")
    print(f"Average waiting time: {average:.2f} ticks")


if __name__ == "__main__":
    main()
