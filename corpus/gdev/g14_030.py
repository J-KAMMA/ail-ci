# task: Use a dataclass with enum-typed field and print a summary grouped by enum value.
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Status(Enum):
    OPEN = "open"
    IN_PROGRESS = "in progress"
    DONE = "done"


@dataclass
class Task:
    task_id: int
    title: str
    priority: Priority
    status: Status = Status.OPEN
    tags: list[str] = field(default_factory=list)

    def summary_line(self) -> str:
        tag_text = ", ".join(self.tags) if self.tags else "-"
        return (
            f"  #{self.task_id:03d} {self.title} "
            f"[status={self.status.value}] [tags={tag_text}]"
        )


def build_tasks() -> list[Task]:
    """Return a fixed, deterministic list of tasks (no input, no randomness)."""
    return [
        Task(1, "Fix login crash", Priority.CRITICAL, Status.IN_PROGRESS, ["auth", "bug"]),
        Task(2, "Update README", Priority.LOW, Status.DONE, ["docs"]),
        Task(3, "Add dark mode", Priority.MEDIUM, Status.OPEN, ["ui", "feature"]),
        Task(4, "Rotate API keys", Priority.HIGH, Status.OPEN, ["security"]),
        Task(5, "Optimize search query", Priority.HIGH, Status.IN_PROGRESS, ["db", "perf"]),
        Task(6, "Typo in footer", Priority.LOW, Status.OPEN, ["ui"]),
        Task(7, "Memory leak in worker", Priority.CRITICAL, Status.OPEN, ["bug", "perf"]),
        Task(8, "Refactor config loader", Priority.MEDIUM, Status.DONE, []),
        Task(9, "Add CSV export", Priority.MEDIUM, Status.IN_PROGRESS, ["feature"]),
        Task(10, "Archive old logs", Priority.LOW, Status.DONE, ["ops"]),
    ]


def group_by_priority(tasks: list[Task]) -> dict[Priority, list[Task]]:
    groups: defaultdict[Priority, list[Task]] = defaultdict(list)
    for task in tasks:
        groups[task.priority].append(task)
    return dict(groups)


def print_summary(tasks: list[Task]) -> None:
    groups = group_by_priority(tasks)
    print(f"Total tasks: {len(tasks)}")
    print("=" * 60)
    for priority in Priority:  # Enum definition order keeps output stable.
        members = groups.get(priority, [])
        print(f"{priority.name} ({priority.value}): {len(members)} task(s)")
        for task in sorted(members, key=lambda t: t.task_id):
            print(task.summary_line())
        if not members:
            print("  (none)")
        print("-" * 60)

    status_counts: dict[Status, int] = {s: 0 for s in Status}
    for task in tasks:
        status_counts[task.status] += 1
    print("Status counts:")
    for status in Status:
        print(f"  {status.name}: {status_counts[status]}")


def main() -> None:
    tasks = build_tasks()
    print_summary(tasks)


if __name__ == "__main__":
    main()
