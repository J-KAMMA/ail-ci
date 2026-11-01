# task: Simulate a parking garage with a fixed number of spaces and seeded vehicle arrivals, then print the peak occupancy reached.
import random
from dataclasses import dataclass
from typing import List


@dataclass
class Vehicle:
    vehicle_id: int
    arrival_time: int
    duration: int


@dataclass
class Garage:
    capacity: int
    occupied: int = 0
    peak: int = 0
    rejected: int = 0

    def enter(self) -> bool:
        if self.occupied >= self.capacity:
            self.rejected += 1
            return False
        self.occupied += 1
        if self.occupied > self.peak:
            self.peak = self.occupied
        return True

    def leave(self) -> None:
        if self.occupied > 0:
            self.occupied -= 1


def generate_vehicles(count: int, max_gap: int, max_duration: int) -> List[Vehicle]:
    vehicles: List[Vehicle] = []
    clock = 0
    for vid in range(1, count + 1):
        clock += random.randint(0, max_gap)
        duration = random.randint(1, max_duration)
        vehicles.append(Vehicle(vid, clock, duration))
    return vehicles


def simulate(vehicles: List[Vehicle], capacity: int) -> Garage:
    garage = Garage(capacity=capacity)
    # Events: (time, order, kind, vehicle_id); departures (kind 0) before arrivals (kind 1) at same time.
    events: List[tuple[int, int, int, int]] = []
    for v in vehicles:
        events.append((v.arrival_time, 1, 1, v.vehicle_id))
        events.append((v.arrival_time + v.duration, 0, 0, v.vehicle_id))
    events.sort()
    for _time, _order, kind, _vid in events:
        if kind == 1:
            garage.enter()
        else:
            garage.leave()
    return garage


def main() -> None:
    random.seed(42)
    capacity = 12
    vehicles = generate_vehicles(count=200, max_gap=5, max_duration=40)
    garage = simulate(vehicles, capacity)
    print(f"Spaces: {capacity}")
    print(f"Vehicles arrived: {len(vehicles)}")
    print(f"Peak occupancy: {garage.peak}")
    print(f"Rejected (garage full): {garage.rejected}")


if __name__ == "__main__":
    main()
