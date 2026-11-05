# task: Create a Counter base class that increments a class-level count on each instance creation and a subclass that tracks its own separate count, printing both totals.
class Counter:
    """Base class that counts how many instances of its own class have been created."""

    count: int = 0

    def __init__(self) -> None:
        cls = type(self)
        cls.count += 1
        self.serial: int = cls.count


class TrackedCounter(Counter):
    """Subclass with its own separate class-level count."""

    count: int = 0


def main() -> None:
    base_instances: list[Counter] = [Counter() for _ in range(3)]
    sub_instances: list[TrackedCounter] = [TrackedCounter() for _ in range(2)]
    more_base: Counter = Counter()

    print(f"Counter total: {Counter.count}")
    print(f"TrackedCounter total: {TrackedCounter.count}")
    print("Base serials:", [obj.serial for obj in base_instances + [more_base]])
    print("Subclass serials:", [obj.serial for obj in sub_instances])


if __name__ == "__main__":
    main()
