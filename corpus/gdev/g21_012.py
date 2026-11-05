# task: Decode a JSON string and print each key-value pair in alphabetical order of keys.
import json
from typing import Any

SAMPLE_JSON: str = """
{
    "zebra": 26,
    "apple": "red",
    "mango": {"color": "yellow", "weight": 0.3},
    "banana": [1, 2, 3],
    "cherry": true,
    "date": null
}
"""


def format_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def main() -> None:
    data: Any = json.loads(SAMPLE_JSON)
    if not isinstance(data, dict):
        raise ValueError("Top-level JSON value must be an object")

    for key, value in sorted(data.items(), key=lambda item: item[0]):
        print(f"{key}: {format_value(value)}")


if __name__ == "__main__":
    main()
