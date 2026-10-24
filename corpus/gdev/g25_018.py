# task: Implement a finite state machine for a simple text-based traffic counter that transitions between IDLE and COUNTING states based on a fixed signal list.
from dataclasses import dataclass, field
from enum import Enum, auto


class State(Enum):
    IDLE = auto()
    COUNTING = auto()


class Signal(Enum):
    START = auto()
    VEHICLE = auto()
    NOISE = auto()
    STOP = auto()


FIXED_SIGNALS: list[str] = [
    "noise",
    "start",
    "vehicle",
    "vehicle",
    "noise",
    "vehicle",
    "stop",
    "vehicle",
    "start",
    "vehicle",
    "vehicle",
    "vehicle",
    "stop",
    "noise",
    "stop",
    "start",
    "stop",
]


@dataclass
class TrafficCounter:
    state: State = State.IDLE
    current_count: int = 0
    completed_sessions: list[int] = field(default_factory=list)

    def handle(self, signal: Signal) -> str:
        """Apply one signal to the state machine and return a description of the action."""
        previous = self.state

        if self.state is State.IDLE:
            if signal is Signal.START:
                self.state = State.COUNTING
                self.current_count = 0
                action = "begin session"
            else:
                action = "ignored"

        elif self.state is State.COUNTING:
            if signal is Signal.VEHICLE:
                self.current_count += 1
                action = f"count -> {self.current_count}"
            elif signal is Signal.STOP:
                self.completed_sessions.append(self.current_count)
                action = f"end session with {self.current_count}"
                self.state = State.IDLE
                self.current_count = 0
            else:
                action = "ignored"

        else:  # pragma: no cover - defensive branch for exhaustive states
            raise RuntimeError(f"Unknown state: {self.state}")

        return f"{previous.name:>8} --{signal.name}--> {self.state.name:<8} ({action})"


def parse_signal(token: str) -> Signal:
    """Map a fixed text token onto a Signal; unknown tokens are treated as noise."""
    mapping: dict[str, Signal] = {
        "start": Signal.START,
        "vehicle": Signal.VEHICLE,
        "stop": Signal.STOP,
        "noise": Signal.NOISE,
    }
    return mapping.get(token, Signal.NOISE)


def main() -> None:
    counter = TrafficCounter()

    print("Traffic counter FSM trace")
    print("-" * 60)
    for index, token in enumerate(FIXED_SIGNALS, start=1):
        signal = parse_signal(token)
        line = counter.handle(signal)
        print(f"{index:02d}. {token:<8} {line}")

    print("-" * 60)
    print(f"Final state: {counter.state.name}")
    print(f"Pending count: {counter.current_count}")
    print(f"Completed sessions: {len(counter.completed_sessions)}")
    for number, total in enumerate(counter.completed_sessions, start=1):
        print(f"  session {number}: {total} vehicle(s)")
    print(f"Total vehicles counted: {sum(counter.completed_sessions)}")


if __name__ == "__main__":
    main()
