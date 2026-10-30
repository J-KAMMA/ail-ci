# task: Simulate two elevators in a building that dispatch each request to the nearest car, then print which elevator serves each request.
from __future__ import annotations

from dataclasses import dataclass, field


TOP_FLOOR = 15
MAX_TICKS = 200


@dataclass
class Elevator:
    name: str
    floor: int = 0
    stops: list[int] = field(default_factory=list)
    assigned: list[tuple[int, int]] = field(default_factory=list)

    def estimated_cost(self, request_floor: int) -> int:
        """Total travel distance if this request is appended to the queue."""
        position = self.floor
        total = 0
        for stop in self.stops:
            total += abs(position - stop)
            position = stop
        total += abs(position - request_floor)
        return total

    def assign(self, request_id: int, request_floor: int) -> None:
        if request_floor not in self.stops:
            self.stops.append(request_floor)
        self.assigned.append((request_id, request_floor))

    def step(self) -> int | None:
        """Move one floor toward the next stop. Return the floor if a stop is reached."""
        if not self.stops:
            return None
        target = self.stops[0]
        if self.floor < target:
            self.floor += 1
        elif self.floor > target:
            self.floor -= 1
        if self.floor == target:
            self.stops.pop(0)
            return self.floor
        return None


@dataclass(frozen=True)
class Request:
    request_id: int
    time: int
    floor: int


def build_requests() -> list[Request]:
    raw: list[tuple[int, int]] = [
        (0, 5),
        (1, 12),
        (2, 3),
        (4, 9),
        (6, 0),
        (7, 14),
        (9, 6),
        (12, 1),
        (13, 10),
        (15, 7),
        (18, 15),
        (20, 4),
    ]
    return [Request(i + 1, t, f) for i, (t, f) in enumerate(raw)]


def dispatch(elevators: list[Elevator], request: Request) -> Elevator:
    """Pick the elevator with the smallest estimated cost; ties go to the earlier car."""
    best = elevators[0]
    best_cost = best.estimated_cost(request.floor)
    for elevator in elevators[1:]:
        cost = elevator.estimated_cost(request.floor)
        if cost < best_cost:
            best = elevator
            best_cost = cost
    return best


def main() -> None:
    elevators = [Elevator("A", floor=0), Elevator("B", floor=TOP_FLOOR)]
    pending = build_requests()
    pending_index = 0

    print(f"Building floors 0..{TOP_FLOOR}; elevators: "
          + ", ".join(f"{e.name} starts at floor {e.floor}" for e in elevators))

    for tick in range(MAX_TICKS):
        # Dispatch requests arriving at this tick.
        while pending_index < len(pending) and pending[pending_index].time == tick:
            request = pending[pending_index]
            chosen = dispatch(elevators, request)
            chosen.assign(request.request_id, request.floor)
            print(f"t={tick:3d}: request #{request.request_id} at floor {request.floor:2d} "
                  f"-> Elevator {chosen.name}")
            pending_index += 1

        # Move every elevator one step.
        for elevator in elevators:
            arrived = elevator.step()
            if arrived is not None:
                print(f"t={tick:3d}: Elevator {elevator.name} stops at floor {arrived:2d}")

        if pending_index >= len(pending) and all(not e.stops for e in elevators):
            print(f"All requests served by t={tick}.")
            break

    print()
    print("Summary:")
    for elevator in elevators:
        floors = [floor for _, floor in elevator.assigned]
        ids = [rid for rid, _ in elevator.assigned]
        print(f"  Elevator {elevator.name}: {len(elevator.assigned)} requests "
              f"(ids {ids}, floors {floors}), final floor {elevator.floor}")


if __name__ == "__main__":
    main()
