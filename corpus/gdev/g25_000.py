# task: Define a Traffic Light Enum with RED, YELLOW, and GREEN, then print the cycle of states for ten transitions starting from RED.
from enum import Enum


class TrafficLight(Enum):
    RED = 1
    YELLOW = 2
    GREEN = 3

    def next_state(self) -> "TrafficLight":
        """Return the state that follows this one in the light cycle."""
        transitions: dict[TrafficLight, TrafficLight] = {
            TrafficLight.RED: TrafficLight.GREEN,
            TrafficLight.GREEN: TrafficLight.YELLOW,
            TrafficLight.YELLOW: TrafficLight.RED,
        }
        return transitions[self]


TRANSITION_COUNT: int = 10


def main() -> None:
    current: TrafficLight = TrafficLight.RED
    print(f"Start: {current.name}")
    for step in range(1, TRANSITION_COUNT + 1):
        following: TrafficLight = current.next_state()
        print(f"Step {step:2d}: {current.name} -> {following.name}")
        current = following
    print(f"Final state: {current.name}")


if __name__ == "__main__":
    main()
