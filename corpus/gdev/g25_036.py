# task: Implement an enum-based priority queue where tasks are ordered by priority levels defined in an Enum and print the processing order.
import heapq
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from itertools import count


class Priority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class Status(Enum):
    PENDING = "pending"
    DONE = "done"


@dataclass(order=False)
class Task:
    name: str
    priority: Priority
    status: Status = field(default=Status.PENDING)

    def __repr__(self) -> str:
        return f"Task({self.name!r}, {self.priority.name})"


class TaskQueue:
    """Priority queue ordered by Priority enum value, FIFO within a level."""

    def __init__(self) -> None:
        self._heap: list[tuple[int, int, Task]] = []
        self._counter = count()

    def push(self, task: Task) -> None:
        entry = (int(task.priority), next(self._counter), task)
        heapq.heappush(self._heap, entry)

    def pop(self) -> Task:
        if not self._heap:
            raise IndexError("pop from empty TaskQueue")
        _, _, task = heapq.heappop(self._heap)
        task.status = Status.DONE
        return task

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)


def build_tasks() -> list[Task]:
    specs: list[tuple[str, Priority]] = [
        ("backup-database", Priority.LOW),
        ("handle-login-outage", Priority.CRITICAL),
        ("update-docs", Priority.BACKGROUND),
        ("review-pull-request", Priority.MEDIUM),
        ("fix-payment-bug", Priority.HIGH),
        ("rotate-certificates", Priority.HIGH),
        ("notify-on-call", Priority.CRITICAL),
        ("clean-temp-files", Priority.BACKGROUND),
        ("refactor-cache", Priority.MEDIUM),
        ("send-weekly-report", Priority.LOW),
    ]
    return [Task(name, prio) for name, prio in specs]


def main() -> None:
    queue = TaskQueue()
    for task in build_tasks():
        queue.push(task)

    print(f"Enqueued {len(queue)} tasks.")
    print("Processing order:")
    position = 1
    while queue:
        task = queue.pop()
        print(f"{position:2d}. [{task.priority.name:<10}] {task.name} -> {task.status.value}")
        position += 1

    print("Queue empty:", not queue)


if __name__ == "__main__":
    main()
