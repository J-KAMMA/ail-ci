# task: Create a dataclass Temperature with a field converter-style normalization in __post_init__ converting Fahrenheit to Celsius.
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Temperature:
    """A temperature reading normalized to Celsius on construction.

    `value` is the reading in the unit given by `scale` ("C" or "F").
    After __post_init__, `celsius` always holds the normalized Celsius value.
    """

    value: float
    scale: str = "C"
    celsius: float = field(init=False)

    def __post_init__(self) -> None:
        scale = self.scale.strip().upper()
        if scale not in ("C", "F"):
            raise ValueError(f"unsupported temperature scale: {self.scale!r}")
        # Normalize the scale name so equality and repr are consistent.
        object.__setattr__(self, "scale", scale)

        if scale == "F":
            celsius = (float(self.value) - 32.0) * 5.0 / 9.0
        else:
            celsius = float(self.value)
        object.__setattr__(self, "celsius", celsius)

    @property
    def fahrenheit(self) -> float:
        return self.celsius * 9.0 / 5.0 + 32.0


def main() -> None:
    samples: list[Temperature] = [
        Temperature(32.0, "F"),
        Temperature(212.0, "f"),
        Temperature(98.6, "F"),
        Temperature(-40.0, "F"),
        Temperature(0.0, "C"),
        Temperature(100.0),
    ]

    for t in samples:
        print(
            f"{t.value:>7.2f} {t.scale} -> {t.celsius:>8.3f} C "
            f"(round-trip {t.fahrenheit:.2f} F)"
        )

    try:
        Temperature(1.0, "K")
    except ValueError as exc:
        print(f"error: {exc}")


if __name__ == "__main__":
    main()
