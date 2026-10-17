import sys
from typing import Callable, Dict, List

Handler = Callable[[int], str]
Observers = Dict[str, List[Handler]]


def register(observers: Observers, event: str, handler: Handler) -> None:
    observers.setdefault(event, []).append(handler)


def emit(observers: Observers, event: str, number: int) -> List[str]:
    return [handler(number) for handler in observers.get(event, [])]


def parity(number: int) -> str:
    return "even" if number % 2 == 0 else "odd"


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    numbers = [int(token) for token in data[1 : 1 + n]]

    observers: Observers = {"even": [], "odd": []}

    register(observers, "even", lambda x: f"{x} is even")
    register(observers, "even", lambda x: f"checked {x}: divisible by 2")
    register(observers, "odd", lambda x: f"{x} is odd")
    register(observers, "odd", lambda x: f"checked {x}: not divisible by 2")

    for number in numbers:
        for output in emit(observers, parity(number), number):
            print(output)


if __name__ == "__main__":
    main()
