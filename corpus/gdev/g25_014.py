# task: Implement a turnstile state machine with LOCKED and UNLOCKED states responding to coin and push events from a fixed event sequence.
from __future__ import annotations

from enum import Enum, auto


class State(Enum):
    LOCKED = auto()
    UNLOCKED = auto()


class Event(Enum):
    COIN = auto()
    PUSH = auto()


class Turnstile:
    """A classic coin-operated turnstile state machine."""

    def __init__(self) -> None:
        self.state: State = State.LOCKED
        self.passes: int = 0
        self.rejected_pushes: int = 0
        self.coins_accepted: int = 0

    def handle(self, event: Event) -> str:
        """Process one event and return a human-readable log line."""
        if self.state is State.LOCKED:
            if event is Event.COIN:
                self.state = State.UNLOCKED
                self.coins_accepted += 1
                return "LOCKED --coin--> UNLOCKED (arm unlocked)"
            self.rejected_pushes += 1
            return "LOCKED --push--> LOCKED (blocked, no coin)"

        # State is UNLOCKED
        if event is Event.PUSH:
            self.state = State.LOCKED
            self.passes += 1
            return "UNLOCKED --push--> LOCKED (passenger passed)"
        # Extra coin while already unlocked: refund-style, stays unlocked.
        self.coins_accepted += 1
        return "UNLOCKED --coin--> UNLOCKED (extra coin, stays unlocked)"


EVENT_SEQUENCE: tuple[Event, ...] = (
    Event.PUSH,
    Event.COIN,
    Event.PUSH,
    Event.PUSH,
    Event.COIN,
    Event.COIN,
    Event.PUSH,
    Event.COIN,
    Event.PUSH,
)


def main() -> None:
    turnstile = Turnstile()
    print(f"Initial state: {turnstile.state.name}")
    for step, event in enumerate(EVENT_SEQUENCE, start=1):
        message = turnstile.handle(event)
        print(f"Step {step:2d}: event={event.name:<4} | {message} | state={turnstile.state.name}")

    print()
    print("Summary:")
    print(f"  Final state:      {turnstile.state.name}")
    print(f"  Coins accepted:   {turnstile.coins_accepted}")
    print(f"  Passes:           {turnstile.passes}")
    print(f"  Blocked pushes:   {turnstile.rejected_pushes}")


if __name__ == "__main__":
    main()
