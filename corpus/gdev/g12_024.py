# task: Simulate an elevator serving a fixed list of floor requests in first-come first-served order across 10 floors, then print the total number of floors traveled.
from typing import Sequence

LOWEST_FLOOR: int = 1
HIGHEST_FLOOR: int = 10
START_FLOOR: int = 1

REQUESTS: list[int] = [5, 3, 9, 2, 10, 1, 7, 7, 4]


def validate_requests(requests: Sequence[int], lowest: int, highest: int) -> None:
    for floor in requests:
        if not lowest <= floor <= highest:
            raise ValueError(
                f"Request floor {floor} is outside the range {lowest}-{highest}"
            )


def simulate_elevator(start: int, requests: Sequence[int]) -> int:
    """Serve requests in first-come first-served order and return floors traveled."""
    current: int = start
    total_floors: int = 0
    for target in requests:
        total_floors += abs(target - current)
        current = target
    return total_floors


def main() -> None:
    validate_requests(REQUESTS, LOWEST_FLOOR, HIGHEST_FLOOR)
    total: int = simulate_elevator(START_FLOOR, REQUESTS)
    print(f"Requests served in order: {REQUESTS}")
    print(f"Total floors traveled: {total}")


if __name__ == "__main__":
    main()
