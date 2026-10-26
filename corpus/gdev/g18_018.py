# task: Use deque.rotate to simulate Josephus elimination on 7 people where every second person is removed, printing the elimination order.
from collections import deque


def josephus_order(n: int) -> tuple[list[int], int]:
    """Simulate Josephus elimination where every second person is removed.

    Returns the elimination order and the survivor.
    """
    circle: deque[int] = deque(range(1, n + 1))
    order: list[int] = []
    while len(circle) > 1:
        # Skip one person (move them to the back), then eliminate the next.
        circle.rotate(-1)
        order.append(circle.popleft())
    return order, circle[0]


def main() -> None:
    n = 7
    order, survivor = josephus_order(n)
    print(f"Josephus elimination on {n} people (every second person removed):")
    for step, person in enumerate(order, start=1):
        print(f"Elimination {step}: person {person}")
    print(f"Survivor: person {survivor}")


if __name__ == "__main__":
    main()
