# task: Implement a Observer base class and two subclasses that react to a fixed sequence of events by printing messages from a Subject class.
from __future__ import annotations

from abc import ABC, abstractmethod


class Observer(ABC):
    """Base class for observers that react to events published by a Subject."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def update(self, event: str, payload: object) -> None:
        """Handle an event emitted by the subject."""


class LoggingObserver(Observer):
    """Observer that prints a log line for every event it receives."""

    def update(self, event: str, payload: object) -> None:
        print(f"[{self.name}] log: event={event!r} payload={payload!r}")


class CounterObserver(Observer):
    """Observer that counts events and prints a running total."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.count = 0

    def update(self, event: str, payload: object) -> None:
        self.count += 1
        print(f"[{self.name}] count: {self.count} (last event: {event})")


class Subject:
    """Maintains a list of observers and notifies them of events."""

    def __init__(self) -> None:
        self._observers: list[Observer] = []

    def attach(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event: str, payload: object = None) -> None:
        for observer in list(self._observers):
            observer.update(event, payload)


def main() -> None:
    subject = Subject()
    logger = LoggingObserver("logger")
    counter = CounterObserver("counter")

    subject.attach(logger)
    subject.attach(counter)

    fixed_events: list[tuple[str, object]] = [
        ("start", None),
        ("data", 42),
        ("data", "hello"),
        ("pause", None),
        ("resume", [1, 2, 3]),
        ("stop", {"reason": "done"}),
    ]

    for event, payload in fixed_events:
        if event == "pause":
            subject.detach(logger)
            print("-- logger detached --")
        elif event == "resume":
            subject.attach(logger)
            print("-- logger reattached --")
        subject.notify(event, payload)

    print(f"Final count: {counter.count}")


if __name__ == "__main__":
    main()
