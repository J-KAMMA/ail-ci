# task: Use dataclasses with __slots__ to compare memory footprint via sys.getsizeof against a regular class instance.
import sys
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class RegularPoint:
    """A plain class: instances carry a per-object __dict__."""

    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z


@dataclass
class PlainDataPoint:
    """A dataclass without __slots__: same layout as RegularPoint."""

    x: float
    y: float
    z: float


@dataclass(slots=True)
class SlottedDataPoint:
    """A dataclass with __slots__ generated automatically (Python 3.10+)."""

    x: float
    y: float
    z: float


def shallow_size(obj: object) -> int:
    """Size of the object itself, as reported by sys.getsizeof."""
    return sys.getsizeof(obj)


def dict_size(obj: object) -> int:
    """Size of the instance __dict__ if one exists, otherwise 0."""
    d = getattr(obj, "__dict__", None)
    return sys.getsizeof(d) if d is not None else 0


def has_instance_dict(obj: object) -> bool:
    return getattr(obj, "__dict__", None) is not None


def total_size(obj: object) -> int:
    """Shallow size plus instance dictionary size (if any)."""
    return shallow_size(obj) + dict_size(obj)


def bulk_footprint(factory: Callable[[float, float, float], object], count: int) -> int:
    """Estimate the memory footprint of `count` instances held in a list."""
    objects = [factory(float(i), float(i * 2), float(i * 3)) for i in range(count)]
    container = sys.getsizeof(objects)
    return container + sum(total_size(o) for o in objects)


def describe_slots_restriction(obj: object) -> str:
    """Report whether arbitrary attribute assignment is rejected."""
    try:
        setattr(obj, "extra", 1.0)
    except AttributeError:
        return "rejected (AttributeError)"
    return "accepted"


def main() -> None:
    print(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print()

    samples: list[tuple[str, object]] = [
        ("RegularPoint", RegularPoint(1.0, 2.0, 3.0)),
        ("PlainDataPoint", PlainDataPoint(1.0, 2.0, 3.0)),
        ("SlottedDataPoint", SlottedDataPoint(1.0, 2.0, 3.0)),
    ]

    print("Single instance sizes (bytes):")
    header = f"{'class':<18}{'getsizeof':>12}{'__dict__':>12}{'total':>12}{'has __dict__':>14}"
    print(header)
    print("-" * len(header))
    for name, obj in samples:
        print(
            f"{name:<18}"
            f"{shallow_size(obj):>12}"
            f"{dict_size(obj):>12}"
            f"{total_size(obj):>12}"
            f"{str(has_instance_dict(obj)):>14}"
        )
    print()

    print("Attribute assignment on new name 'extra':")
    for name, obj in samples:
        print(f"  {name:<18} {describe_slots_restriction(obj)}")
    print()

    count = 1000
    factories: list[tuple[str, Callable[[float, float, float], object]]] = [
        ("RegularPoint", RegularPoint),
        ("PlainDataPoint", PlainDataPoint),
        ("SlottedDataPoint", SlottedDataPoint),
    ]
    print(f"Estimated footprint of {count} instances in a list (bytes):")
    baseline = bulk_footprint(RegularPoint, count)
    for name, factory in factories:
        size = bulk_footprint(factory, count)
        ratio = size / baseline
        print(f"  {name:<18}{size:>12}   ratio vs RegularPoint: {ratio:.3f}")
    print()

    slotted = SlottedDataPoint(1.0, 2.0, 3.0)
    regular = RegularPoint(1.0, 2.0, 3.0)
    saving = total_size(regular) - total_size(slotted)
    print(f"Per-instance saving of SlottedDataPoint over RegularPoint: {saving} bytes")


if __name__ == "__main__":
    main()
