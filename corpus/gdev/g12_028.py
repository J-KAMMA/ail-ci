# task: Simulate an elevator with an eight-passenger capacity limit receiving a fixed sequence of boarding requests, then print each request that was refused.
from dataclasses import dataclass


CAPACITY: int = 8


@dataclass(frozen=True)
class BoardingRequest:
    """A request by a group of passengers to board the elevator."""
    group_name: str
    size: int


class Elevator:
    """An elevator that admits whole groups only if they fit within capacity."""

    def __init__(self, capacity: int) -> None:
        self.capacity: int = capacity
        self.occupancy: int = 0

    def try_board(self, request: BoardingRequest) -> bool:
        """Admit the group if all its members fit; return True if accepted."""
        if self.occupancy + request.size <= self.capacity:
            self.occupancy += request.size
            return True
        return False


def build_requests() -> list[BoardingRequest]:
    """Return the fixed sequence of boarding requests."""
    return [
        BoardingRequest("Alpha", 2),
        BoardingRequest("Bravo", 1),
        BoardingRequest("Charlie", 3),
        BoardingRequest("Delta", 2),
        BoardingRequest("Echo", 1),
        BoardingRequest("Foxtrot", 2),
        BoardingRequest("Golf", 1),
        BoardingRequest("Hotel", 3),
        BoardingRequest("India", 1),
        BoardingRequest("Juliet", 4),
        BoardingRequest("Kilo", 1),
        BoardingRequest("Lima", 2),
    ]


def main() -> None:
    elevator = Elevator(CAPACITY)
    requests = build_requests()
    refused: list[BoardingRequest] = []

    for request in requests:
        if elevator.try_board(request):
            print(
                f"Accepted {request.group_name} ({request.size}); "
                f"occupancy now {elevator.occupancy}/{elevator.capacity}"
            )
        else:
            refused.append(request)

    print()
    print(f"Refused requests: {len(refused)}")
    for request in refused:
        print(f"Refused {request.group_name} ({request.size})")


if __name__ == "__main__":
    main()
