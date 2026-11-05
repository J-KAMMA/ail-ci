# task: Serialize a float-heavy dictionary with a fixed rounding function applied before dumping to JSON and print the result.
import json
import math
from typing import Any


def round_floats(value: Any, ndigits: int = 3) -> Any:
    """Recursively round every float in a nested structure to ndigits places."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return value
        rounded = round(value, ndigits)
        # Normalize negative zero so output is stable.
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, dict):
        return {key: round_floats(item, ndigits) for key, item in value.items()}
    if isinstance(value, list):
        return [round_floats(item, ndigits) for item in value]
    if isinstance(value, tuple):
        return tuple(round_floats(item, ndigits) for item in value)
    return value


def build_data() -> dict[str, Any]:
    """Construct a deterministic, float-heavy dictionary without any input."""
    data: dict[str, Any] = {}
    for i in range(1, 6):
        key = f"sensor_{i:02d}"
        data[key] = {
            "mean": math.sqrt(i) / 3.0,
            "variance": math.pi * i / 7.0,
            "samples": [math.sin(i * k) * 1.2345678 for k in range(1, 4)],
            "scale": 10.0 ** (-i) * math.e,
        }
    data["metadata"] = {
        "ratio": 2.0 / 3.0,
        "offset": -0.000123456,
        "bounds": (0.5 / 7.0, 99.99999 / 3.0),
    }
    return data


def main() -> None:
    raw = build_data()
    rounded = round_floats(raw, ndigits=3)
    text = json.dumps(rounded, indent=2, sort_keys=True)
    print(text)


if __name__ == "__main__":
    main()
