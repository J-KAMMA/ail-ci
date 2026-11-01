# task: Write a script that uses a deque to simulate a fixed sequence of push and pop operations on a hardcoded list and prints the state after each operation.
from collections import deque
from typing import Any


def describe_state(dq: deque[Any]) -> str:
    return "[" + ", ".join(repr(item) for item in dq) + "]"


def main() -> None:
    values: list[int | str] = [10, 20, 30, "alpha", 40]
    operations: list[tuple[str, str, int | str | None]] = [
        ("push_back", "", values[0]),
        ("push_back", "", values[1]),
        ("push_front", "", values[2]),
        ("push_back", "", values[3]),
        ("pop_front", "", None),
        ("push_front", "", values[4]),
        ("pop_back", "", None),
        ("pop_front", "", None),
        ("push_back", "", 50),
        ("pop_back", "", None),
        ("pop_back", "", None),
        ("pop_front", "", None),
    ]

    dq: deque[Any] = deque()
    print(f"Initial state: {describe_state(dq)}")

    for step, (op, _, arg) in enumerate(operations, start=1):
        if op == "push_back":
            dq.append(arg)
            print(f"Step {step:2d}: push_back({arg!r})  -> {describe_state(dq)}")
        elif op == "push_front":
            dq.appendleft(arg)
            print(f"Step {step:2d}: push_front({arg!r}) -> {describe_state(dq)}")
        elif op == "pop_back":
            if dq:
                removed = dq.pop()
                print(f"Step {step:2d}: pop_back()   -> removed {removed!r}, state {describe_state(dq)}")
            else:
                print(f"Step {step:2d}: pop_back()   -> deque empty, state {describe_state(dq)}")
        elif op == "pop_front":
            if dq:
                removed = dq.popleft()
                print(f"Step {step:2d}: pop_front()  -> removed {removed!r}, state {describe_state(dq)}")
            else:
                print(f"Step {step:2d}: pop_front()  -> deque empty, state {describe_state(dq)}")

    print(f"Final length: {len(dq)}")


if __name__ == "__main__":
    main()
