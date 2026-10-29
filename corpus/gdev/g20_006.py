# task: Write a script that uses re.sub with a replacement function to convert all hardcoded Celsius temperatures in a string to Fahrenheit with one decimal place.
import re
from typing import Final

# Matches a number followed by a Celsius unit: "25°C", "25 °C", "25º C",
# "-3.5 C", or "100 degrees Celsius". The trailing \b prevents matching
# words such as "Celsius" or "CM" when using the bare "C" form.
CELSIUS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<value>[-+]?\d+(?:\.\d+)?)\s*"
    r"(?:°\s*C\b|º\s*C\b|degrees?\s+Celsius\b|C\b)"
)

SAMPLE_TEXT: Final[str] = (
    "Morning low was -3.5 C, rising to 12°C by noon.\n"
    "The lab stays at 22 °C, while the oven hits 180º C.\n"
    "Water boils at 100 degrees Celsius and freezes at 0°C.\n"
    "Body temperature is about 37 degrees Celsius.\n"
    "Note: the CM ruler and Celsius scale are unrelated to 5 Cats."
)


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert a Celsius temperature to Fahrenheit."""
    return celsius * 9.0 / 5.0 + 32.0


def replace_celsius(match: re.Match[str]) -> str:
    """Replacement function for re.sub: converts a Celsius match to Fahrenheit."""
    celsius = float(match.group("value"))
    fahrenheit = celsius_to_fahrenheit(celsius)
    # Avoid printing "-0.0" when rounding yields zero.
    if round(fahrenheit, 1) == 0.0:
        fahrenheit = 0.0
    return f"{fahrenheit:.1f}°F"


def convert_text(text: str) -> str:
    """Return text with every hardcoded Celsius temperature converted to Fahrenheit."""
    return CELSIUS_PATTERN.sub(replace_celsius, text)


def main() -> None:
    converted = convert_text(SAMPLE_TEXT)
    print(converted)


if __name__ == "__main__":
    main()
