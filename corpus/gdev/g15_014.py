# task: Simulate a timeout by having a function raise TimeoutError after a fixed number of simulated steps, and catch it in the caller.
from typing import Iterable


class Step:
    """A single simulated step with a label and cost."""

    def __init__(self, label: str, cost: int) -> None:
        self.label = label
        self.cost = cost


def run_with_budget(steps: Iterable[Step], budget: int) -> list[str]:
    """Execute steps, raising TimeoutError once the simulated budget is exhausted."""
    elapsed = 0
    completed: list[str] = []
    for step in steps:
        if elapsed + step.cost > budget:
            raise TimeoutError(
                f"timeout after {elapsed} simulated steps "
                f"(budget {budget}, next step '{step.label}' costs {step.cost})"
            )
        elapsed += step.cost
        completed.append(step.label)
    return completed


def build_steps() -> list[Step]:
    """Build a fixed, deterministic list of simulated steps."""
    costs = [3, 1, 4, 1, 5, 9, 2, 6]
    return [Step(f"step-{i}", c) for i, c in enumerate(costs)]


def caller(budget: int) -> str:
    """Call the simulated operation and catch its timeout."""
    try:
        done = run_with_budget(build_steps(), budget)
    except TimeoutError as exc:
        return f"caught: {exc}"
    return f"finished: {', '.join(done)}"


def main() -> None:
    for budget in (5, 12, 25, 100):
        print(f"budget={budget}")
        print(f"  {caller(budget)}")


if __name__ == "__main__":
    main()
