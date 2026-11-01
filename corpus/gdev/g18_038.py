# task: Use a deque with maxlen to keep the last five events of a hardcoded event stream and print the buffer after each insertion.
from collections import deque
from typing import Deque


def main() -> None:
    # Hardcoded event stream (deterministic, no input read).
    events: list[str] = [
        "login:alice",
        "click:button_a",
        "scroll:page_1",
        "click:button_b",
        "logout:alice",
        "login:bob",
        "click:link_x",
        "scroll:page_2",
        "error:timeout",
        "logout:bob",
    ]

    buffer: Deque[str] = deque(maxlen=5)

    for event in events:
        buffer.append(event)
        print(f"After inserting {event!r}: {list(buffer)}")


if __name__ == "__main__":
    main()
