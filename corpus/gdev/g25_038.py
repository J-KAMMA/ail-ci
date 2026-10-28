# task: Use a match statement to convert a fixed list of temperature readings tagged with units into Celsius and print the results.
from typing import Final

# Fixed temperature readings: (value, unit)
READINGS: Final[list[tuple[float, str]]] = [
    (25.0, "C"),
    (77.0, "F"),
    (300.0, "K"),
    (-40.0, "F"),
    (0.0, "K"),
    (100.0, "C"),
    (98.6, "F"),
    (-273.15, "C"),
    (451.0, "F"),
    (373.15, "K"),
    (42.0, "X"),
]


def to_celsius(value: float, unit: str) -> float | None:
    """Convert a temperature to Celsius using a match statement.

    Returns None for unknown units.
    """
    match unit:
        case "C":
            return value
        case "F":
            return (value - 32.0) * 5.0 / 9.0
        case "K":
            return value - 273.15
        case _:
            return None


def describe(value: float, unit: str) -> str:
    """Return a human-readable description of a reading in Celsius."""
    celsius = to_celsius(value, unit)
    match celsius:
        case None:
            return f"{value:.2f}{unit}: unknown unit, cannot convert"
        case c if c < -273.15:
            return f"{value:.2f}{unit} -> {c:.2f} C: below absolute zero (invalid)"
        case c if c < 0.0:
            return f"{value:.2f}{unit} -> {c:.2f} C: freezing range"
        case c if c < 100.0:
            return f"{value:.2f}{unit} -> {c:.2f} C: liquid range"
        case c:
            return f"{value:.2f}{unit} -> {c:.2f} C: at or above boiling"


def main() -> None:
    print("Temperature readings converted to Celsius:")
    for value, unit in READINGS:
        print(describe(value, unit))


if __name__ == "__main__":
    main()
