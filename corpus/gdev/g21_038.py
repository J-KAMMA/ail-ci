# task: Encode a list of floats rounded to three decimal places and print the JSON array along with its character length.
import json


def encode_rounded_floats(values: list[float], places: int = 3) -> str:
    """Round each float to the given number of decimal places and encode as a JSON array."""
    rounded: list[float] = [round(v, places) for v in values]
    return json.dumps(rounded)


def main() -> None:
    values: list[float] = [
        3.14159,
        2.71828,
        1.41421,
        0.57721,
        -1.23456,
        100.0,
        0.0005,
        -0.0004,
        2.5,
        1 / 3,
    ]

    encoded: str = encode_rounded_floats(values)
    print(encoded)
    print(f"Length: {len(encoded)}")


if __name__ == "__main__":
    main()
