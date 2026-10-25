# task: Write a script that uses re.findall to extract all floating-point numbers, including negative and scientific notation, from a hardcoded text and prints their sum.
import math
import re


TEXT: str = """
Sensor readings for the morning batch:
temperature = -12.5, pressure = 1.013e5, humidity = 47.25%
drift: -3.5E-2, offset: +.5, gain: 2.0e-3
calibration constants: 6.02e23, -1.6e-19, 9.81
noise floor at -0.125 and peak at 4.5e+1, ratio 1.
misc: 1e3, -7., 0.0, -4.2E+02 and .75
"""

FLOAT_PATTERN: re.Pattern[str] = re.compile(
    r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?"
)


def extract_numbers(text: str) -> list[float]:
    """Return all signed decimal/scientific-notation numbers found in text."""
    return [float(match) for match in FLOAT_PATTERN.findall(text)]


def main() -> None:
    numbers: list[float] = extract_numbers(TEXT)

    print(f"Found {len(numbers)} numbers:")
    for value in numbers:
        print(f"  {value!r}")

    total: float = math.fsum(numbers)
    print(f"Sum: {total:.10g}")


if __name__ == "__main__":
    main()
