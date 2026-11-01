# task: Implement a retry-with-backoff state machine with states TRYING, WAITING, SUCCESS, and FAILED, simulating a fixed sequence of outcomes.
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class State(Enum):
    TRYING = "TRYING"
    WAITING = "WAITING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class BackoffPolicy:
    base_delay: float
    factor: float
    max_delay: float

    def delay_after(self, failed_attempts: int) -> float:
        """Exponential backoff: base * factor^(n-1), capped at max_delay."""
        raw = self.base_delay * (self.factor ** (failed_attempts - 1))
        return min(raw, self.max_delay)


@dataclass
class RetryMachine:
    policy: BackoffPolicy
    max_attempts: int
    outcomes: list[bool]  # fixed sequence: True = attempt succeeds
    state: State = State.TRYING
    attempts: int = 0
    clock: float = 0.0
    pending_delay: float = 0.0
    _cursor: int = 0
    trace: list[str] = field(default_factory=list)

    def is_terminal(self) -> bool:
        return self.state in (State.SUCCESS, State.FAILED)

    def _next_outcome(self) -> bool:
        if self._cursor < len(self.outcomes):
            value = self.outcomes[self._cursor]
            self._cursor += 1
            return value
        # Scripted outcomes exhausted: every further attempt fails.
        return False

    def _transition(self, new_state: State, note: str) -> None:
        self.trace.append(
            f"t={self.clock:6.1f}  {self.state.name:<8} -> {new_state.name:<8} {note}"
        )
        self.state = new_state

    def step(self) -> None:
        if self.state is State.TRYING:
            self.attempts += 1
            if self._next_outcome():
                self._transition(State.SUCCESS, f"attempt {self.attempts} succeeded")
            elif self.attempts >= self.max_attempts:
                self._transition(
                    State.FAILED,
                    f"attempt {self.attempts} failed, no attempts left",
                )
            else:
                self.pending_delay = self.policy.delay_after(self.attempts)
                self._transition(
                    State.WAITING,
                    f"attempt {self.attempts} failed, backoff {self.pending_delay:.1f}",
                )
        elif self.state is State.WAITING:
            self.clock += self.pending_delay
            self._transition(State.TRYING, "backoff elapsed")
        # Terminal states: nothing to do.

    def run(self, step_limit: int = 1000) -> None:
        steps = 0
        while not self.is_terminal():
            if steps >= step_limit:
                raise RuntimeError("step limit exceeded; machine did not terminate")
            self.step()
            steps += 1


def run_scenario(label: str, machine: RetryMachine) -> None:
    print(f"== {label} ==")
    machine.run()
    for line in machine.trace:
        print(line)
    print(
        f"final state: {machine.state.name}, "
        f"attempts: {machine.attempts}, "
        f"simulated time: {machine.clock:.1f}"
    )
    print()


def main() -> None:
    policy = BackoffPolicy(base_delay=1.0, factor=2.0, max_delay=5.0)

    run_scenario(
        "Succeeds on third attempt",
        RetryMachine(policy=policy, max_attempts=5, outcomes=[False, False, True]),
    )

    run_scenario(
        "Exhausts all attempts",
        RetryMachine(policy=policy, max_attempts=4, outcomes=[False, False, False, False, True]),
    )

    run_scenario(
        "Succeeds immediately",
        RetryMachine(policy=policy, max_attempts=3, outcomes=[True]),
    )


if __name__ == "__main__":
    main()
