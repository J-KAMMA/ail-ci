# task: Convert a list of strings to floats, substituting NaN for each invalid entry, and print the resulting list.
import math


def to_float_or_nan(text: str) -> float:
    """Convert a string to a float, returning NaN if the conversion fails."""
    try:
        return float(text)
    except ValueError:
        return math.nan


def convert_all(items: list[str]) -> list[float]:
    """Convert each string in the list to a float, substituting NaN for invalid entries."""
    return [to_float_or_nan(item) for item in items]


def main() -> None:
    samples: list[str] = [
        "3.14",
        "  42 ",
        "-0.5",
        "1e3",
        "abc",
        "",
        "12.3.4",
        "+7",
        "inf",
        "1_000.5",
        "not a number",
        "2.718281828",
    ]
    result: list[float] = convert_all(samples)
    print(result)


if __name__ == "__main__":
    main()
