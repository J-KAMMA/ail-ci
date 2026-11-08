# task: Use itertools.cycle with islice to simulate a round-robin assignment of 7 hardcoded tasks to 3 named workers and print the schedule.
from itertools import cycle, islice
from typing import Iterable


def round_robin_schedule(tasks: Iterable[str], workers: Iterable[str]) -> list[tuple[str, str]]:
    """Assign tasks to workers in round-robin order, returning (worker, task) pairs."""
    worker_cycle = cycle(workers)
    return [(worker, task) for task, worker in zip(tasks, worker_cycle)]


def main() -> None:
    tasks: list[str] = [
        "Write design doc",
        "Set up database",
        "Implement API",
        "Build login page",
        "Write unit tests",
        "Configure CI pipeline",
        "Review pull requests",
    ]
    workers: list[str] = ["Alice", "Bob", "Carol"]

    # islice is used to take exactly as many worker slots as there are tasks.
    worker_slots = list(islice(cycle(workers), len(tasks)))
    schedule = list(zip(worker_slots, tasks))

    print("Round-robin schedule:")
    print("-" * 44)
    print(f"{'Slot':<6}{'Worker':<10}{'Task':<24}")
    print("-" * 44)
    for slot, (worker, task) in enumerate(schedule, start=1):
        print(f"{slot:<6}{worker:<10}{task:<24}")
    print("-" * 44)

    print("\nTasks per worker:")
    for worker in workers:
        count = sum(1 for w, _ in schedule if w == worker)
        print(f"  {worker}: {count}")


if __name__ == "__main__":
    main()
