# task: Use json.dumps with allow_nan=False and catch the ValueError raised when serializing a float NaN, then print the error message.
import json
import math


def main() -> None:
    value: float = math.nan
    try:
        json.dumps(value, allow_nan=False)
    except ValueError as exc:
        print(exc)


if __name__ == "__main__":
    main()
