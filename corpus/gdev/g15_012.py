# task: Simulate a task queue where failing jobs are caught and recorded by exception type name while the remaining jobs continue processing.
from __future__ import annotations

import random
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Job:
    job_id: int
    name: str
    action: Callable[[], object]


@dataclass
class JobResult:
    job_id: int
    name: str
    ok: bool
    value: object = None
    error_type: str | None = None
    error_message: str | None = None


@dataclass
class TaskQueue:
    jobs: deque[Job] = field(default_factory=deque)
    results: list[JobResult] = field(default_factory=list)
    error_counts: Counter[str] = field(default_factory=Counter)

    def submit(self, job: Job) -> None:
        self.jobs.append(job)

    def run(self) -> None:
        while self.jobs:
            job = self.jobs.popleft()
            try:
                value = job.action()
            except Exception as exc:  # each failure is recorded, processing continues
                type_name = type(exc).__name__
                self.error_counts[type_name] += 1
                self.results.append(
                    JobResult(
                        job_id=job.job_id,
                        name=job.name,
                        ok=False,
                        error_type=type_name,
                        error_message=str(exc),
                    )
                )
            else:
                self.results.append(
                    JobResult(job_id=job.job_id, name=job.name, ok=True, value=value)
                )


def make_jobs(seed: int = 42, count: int = 12) -> list[Job]:
    rng = random.Random(seed)

    def compute(n: int) -> Callable[[], object]:
        return lambda: 100 // n

    def parse(text: str) -> Callable[[], object]:
        return lambda: int(text)

    def lookup(key: str, table: dict[str, int]) -> Callable[[], object]:
        return lambda: table[key]

    def load(path: str) -> Callable[[], object]:
        return lambda: open(path, encoding="utf-8").read()

    table = {"alpha": 1, "beta": 2, "gamma": 3}
    texts = ["7", "x1", "12", "3.5", "-4", "", "99"]
    keys = ["alpha", "beta", "delta", "gamma"]
    paths = ["/nonexistent/a.txt", "/nonexistent/b.txt"]

    jobs: list[Job] = []
    for i in range(count):
        kind = rng.choice(["compute", "parse", "lookup", "load", "ok"])
        if kind == "compute":
            divisor = rng.randint(0, 4)
            jobs.append(Job(i, f"compute-{divisor}", compute(divisor)))
        elif kind == "parse":
            text = rng.choice(texts)
            jobs.append(Job(i, f"parse-{text!r}", parse(text)))
        elif kind == "lookup":
            key = rng.choice(keys)
            jobs.append(Job(i, f"lookup-{key}", lookup(key, table)))
        elif kind == "load":
            path = rng.choice(paths)
            jobs.append(Job(i, f"load-{path.rsplit('/', 1)[-1]}", load(path)))
        else:
            value = rng.randint(1, 1000)
            jobs.append(Job(i, f"ok-{value}", lambda v=value: v * 2))
    return jobs


def main() -> None:
    random.seed(0)  # seeds global RNG as a precaution; job generation uses its own seeded Random
    queue = TaskQueue()
    for job in make_jobs(seed=42, count=12):
        queue.submit(job)

    queue.run()

    print("Results:")
    for result in queue.results:
        if result.ok:
            print(f"  [{result.job_id:02d}] {result.name}: OK -> {result.value!r}")
        else:
            print(
                f"  [{result.job_id:02d}] {result.name}: FAILED "
                f"{result.error_type}: {result.error_message}"
            )

    succeeded = sum(1 for r in queue.results if r.ok)
    failed = len(queue.results) - succeeded
    print()
    print(f"Total: {len(queue.results)}  succeeded: {succeeded}  failed: {failed}")
    print("Failures by exception type:")
    for type_name in sorted(queue.error_counts):
        print(f"  {type_name}: {queue.error_counts[type_name]}")


if __name__ == "__main__":
    main()
