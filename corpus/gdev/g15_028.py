# task: Use nested try/finally blocks to log the order in which simulated resources are released when a setup step fails.
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ReleaseLog:
    """Records the order in which simulated resources are released."""

    entries: list[str] = field(default_factory=list)

    def record(self, message: str) -> None:
        self.entries.append(message)
        logging.info(message)


@dataclass
class SimulatedResource:
    """A fake resource that logs its acquisition and release."""

    name: str
    log: ReleaseLog
    released: bool = False

    def acquire(self) -> None:
        self.log.record(f"acquired {self.name}")

    def release(self) -> None:
        if not self.released:
            self.released = True
            self.log.record(f"released {self.name}")


def setup_step(fail_at: str | None, log: ReleaseLog) -> None:
    """Acquire several resources in nested try/finally blocks.

    If fail_at names a resource, the setup step raises after acquiring
    that resource, which triggers the unwinding of all enclosing finally
    blocks in reverse order of acquisition.
    """
    db = SimulatedResource("database", log)
    db.acquire()
    try:
        cache = SimulatedResource("cache", log)
        cache.acquire()
        try:
            queue = SimulatedResource("queue", log)
            queue.acquire()
            try:
                log.record("running setup body")
                if fail_at is not None:
                    raise RuntimeError(f"setup failed while holding {fail_at}")
                log.record("setup body completed")
                # Simulate a second failure point after the queue is acquired.
                if fail_at == "queue-post":
                    raise RuntimeError("setup failed after queue body")
            finally:
                queue.release()
        finally:
            cache.release()
    finally:
        db.release()


def run_scenario(title: str, fail_at: str | None, log: ReleaseLog) -> None:
    """Run one scenario and report the release order it produced."""
    print(f"== {title} ==")
    start = len(log.entries)
    try:
        setup_step(fail_at, log)
    except RuntimeError as exc:
        print(f"caught: {exc}")
    else:
        print("setup succeeded")
    for entry in log.entries[start:]:
        print(f"  {entry}")
    releases = [e.removeprefix("released ") for e in log.entries[start:]
                if e.startswith("released ")]
    print(f"  release order: {', '.join(releases)}")
    print()


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        stream=sys.stderr,
        format="%(levelname)s %(message)s",
    )
    log = ReleaseLog()
    scenarios: list[tuple[str, str | None]] = [
        ("success path", None),
        ("fail while holding cache", "cache"),
        ("fail after queue acquired", "queue-post"),
    ]
    for title, fail_at in scenarios:
        run_scenario(title, fail_at, log)


if __name__ == "__main__":
    main()
