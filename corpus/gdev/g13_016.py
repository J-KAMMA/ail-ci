# task: Build a Sensor base class with a read method returning a fixed value and TemperatureSensor subclass that converts the reading to Fahrenheit, printing results.
from __future__ import annotations


class Sensor:
    """Base sensor that returns a fixed raw reading."""

    def __init__(self, name: str, fixed_value: float) -> None:
        self.name = name
        self._fixed_value = fixed_value

    def read(self) -> float:
        """Return the sensor's fixed reading."""
        return self._fixed_value

    def describe(self) -> str:
        return f"{self.name}: {self.read():.2f}"


class TemperatureSensor(Sensor):
    """Sensor that interprets its reading as Celsius and converts to Fahrenheit."""

    def read_celsius(self) -> float:
        return super().read()

    def read_fahrenheit(self) -> float:
        celsius = self.read_celsius()
        return celsius * 9.0 / 5.0 + 32.0

    def describe(self) -> str:
        return (
            f"{self.name}: {self.read_celsius():.2f} C = "
            f"{self.read_fahrenheit():.2f} F"
        )


def main() -> None:
    base = Sensor("generic", 42.0)
    print(base.describe())
    print(f"raw read: {base.read()}")

    temperature_readings: list[TemperatureSensor] = [
        TemperatureSensor("freezing", 0.0),
        TemperatureSensor("room", 21.5),
        TemperatureSensor("boiling", 100.0),
    ]

    for sensor in temperature_readings:
        print(sensor.describe())
        print(f"  fahrenheit: {sensor.read_fahrenheit():.1f}")


if __name__ == "__main__":
    main()
