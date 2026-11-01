# task: Use enum to represent units of measurement and write a converter that prints conversions of a fixed set of values between those units.
from enum import Enum
from typing import Final


class LinearUnit(Enum):
    """Base for units that convert by multiplying with a factor to a base unit.

    Each member's value is a (symbol, factor_to_base_unit) pair.
    """

    @property
    def symbol(self) -> str:
        symbol, _ = self.value
        return symbol

    @property
    def factor(self) -> float:
        _, factor = self.value
        return factor


class Length(LinearUnit):
    METER = ("m", 1.0)
    KILOMETER = ("km", 1000.0)
    CENTIMETER = ("cm", 0.01)
    FOOT = ("ft", 0.3048)
    INCH = ("in", 0.0254)
    MILE = ("mi", 1609.344)


class Mass(LinearUnit):
    KILOGRAM = ("kg", 1.0)
    GRAM = ("g", 0.001)
    POUND = ("lb", 0.45359237)
    OUNCE = ("oz", 0.028349523125)


class Temperature(Enum):
    CELSIUS = "°C"
    FAHRENHEIT = "°F"
    KELVIN = "K"

    @property
    def symbol(self) -> str:
        return self.value


KELVIN_OFFSET: Final[float] = 273.15


def convert_linear(value: float, src: LinearUnit, dst: LinearUnit) -> float:
    """Convert a value between two units of the same linear dimension."""
    if type(src) is not type(dst):
        raise ValueError(f"Cannot convert {src.symbol} to {dst.symbol}: different dimensions")
    return value * src.factor / dst.factor


def to_kelvin(value: float, unit: Temperature) -> float:
    if unit is Temperature.CELSIUS:
        return value + KELVIN_OFFSET
    if unit is Temperature.FAHRENHEIT:
        return (value - 32.0) * 5.0 / 9.0 + KELVIN_OFFSET
    return value


def from_kelvin(kelvin: float, unit: Temperature) -> float:
    if unit is Temperature.CELSIUS:
        return kelvin - KELVIN_OFFSET
    if unit is Temperature.FAHRENHEIT:
        return (kelvin - KELVIN_OFFSET) * 9.0 / 5.0 + 32.0
    return kelvin


def convert_temperature(value: float, src: Temperature, dst: Temperature) -> float:
    return from_kelvin(to_kelvin(value, src), dst)


def format_line(value: float, src_symbol: str, result: float, dst_symbol: str) -> str:
    return f"{value:>10g} {src_symbol:<3} = {result:>14.6f} {dst_symbol}"


def print_linear_section(title: str, units: type[LinearUnit], samples: list[tuple[float, LinearUnit]]) -> None:
    print(f"== {title} ==")
    for value, src in samples:
        for dst in units:
            result = convert_linear(value, src, dst)
            print(format_line(value, src.symbol, result, dst.symbol))
        print()


def print_temperature_section(samples: list[tuple[float, Temperature]]) -> None:
    print("== Temperature ==")
    for value, src in samples:
        for dst in Temperature:
            result = convert_temperature(value, src, dst)
            print(format_line(value, src.symbol, result, dst.symbol))
        print()


def main() -> None:
    length_samples: list[tuple[float, LinearUnit]] = [
        (1.0, Length.MILE),
        (100.0, Length.FOOT),
        (2.5, Length.KILOMETER),
    ]
    mass_samples: list[tuple[float, LinearUnit]] = [
        (1.0, Mass.POUND),
        (500.0, Mass.GRAM),
        (16.0, Mass.OUNCE),
    ]
    temperature_samples: list[tuple[float, Temperature]] = [
        (0.0, Temperature.CELSIUS),
        (212.0, Temperature.FAHRENHEIT),
        (300.0, Temperature.KELVIN),
    ]

    print_linear_section("Length", Length, length_samples)
    print_linear_section("Mass", Mass, mass_samples)
    print_temperature_section(temperature_samples)


if __name__ == "__main__":
    main()
