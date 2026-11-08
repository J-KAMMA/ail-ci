# task: Write a dictionary to a JSON file in a temporary directory, read it back, and print whether the round-trip data matches the original.
import json
import os
import tempfile
from typing import Any


def build_sample_data() -> dict[str, Any]:
    return {
        "name": "round-trip-test",
        "version": 3,
        "pi": 3.14159,
        "active": True,
        "tags": ["alpha", "beta", "gamma"],
        "nested": {
            "count": 42,
            "ratio": 0.5,
            "items": [1, 2, 3],
            "empty": {},
            "nothing": None,
        },
    }


def write_json(path: str, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def read_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        loaded: dict[str, Any] = json.load(f)
    return loaded


def main() -> None:
    original = build_sample_data()

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "data.json")
        write_json(file_path, original)
        round_tripped = read_json(file_path)
        print(f"File written: {os.path.basename(file_path)}")

    matches = original == round_tripped
    print(f"Round-trip data matches original: {matches}")

    if not matches:
        print(f"Original: {json.dumps(original, sort_keys=True)}")
        print(f"Loaded:   {json.dumps(round_tripped, sort_keys=True)}")


if __name__ == "__main__":
    main()
