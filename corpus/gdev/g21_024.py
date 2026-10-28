# task: Convert a list of dictionaries to a JSON string and then flatten it into a CSV-formatted string printed to the console.
import csv
import io
import json
from typing import Any


def build_sample_data() -> list[dict[str, Any]]:
    """Return a fixed, deterministic list of nested dictionaries."""
    return [
        {
            "id": 1,
            "name": "Alice",
            "active": True,
            "address": {"city": "Berlin", "zip": "10115"},
            "tags": ["admin", "developer"],
            "scores": {"math": 91, "science": 88},
        },
        {
            "id": 2,
            "name": "Bob",
            "active": False,
            "address": {"city": "Paris", "zip": "75001"},
            "tags": ["designer"],
            "scores": {"math": 76, "art": 95},
        },
        {
            "id": 3,
            "name": "Chandra",
            "active": True,
            "address": None,
            "tags": [],
            "scores": {},
        },
    ]


def to_json_string(records: list[dict[str, Any]]) -> str:
    """Serialize records to a deterministic, indented JSON string."""
    return json.dumps(records, indent=2, sort_keys=True)


def flatten(obj: Any, prefix: str = "", sep: str = ".") -> dict[str, Any]:
    """Flatten nested dicts and lists into a single-level dict of dotted keys."""
    result: dict[str, Any] = {}

    if isinstance(obj, dict):
        if not obj and prefix:
            result[prefix] = "{}"
            return result
        for key in sorted(obj):
            new_key = f"{prefix}{sep}{key}" if prefix else str(key)
            result.update(flatten(obj[key], new_key, sep))

    elif isinstance(obj, list):
        if not obj and prefix:
            result[prefix] = "[]"
            return result
        for index, item in enumerate(obj):
            new_key = f"{prefix}{sep}{index}" if prefix else str(index)
            result.update(flatten(item, new_key, sep))

    else:
        result[prefix] = "" if obj is None else obj

    return result


def json_to_flat_rows(json_text: str) -> list[dict[str, Any]]:
    """Parse a JSON array of objects and flatten each element."""
    parsed: Any = json.loads(json_text)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON array of objects.")
    return [flatten(item) for item in parsed]


def rows_to_csv_string(rows: list[dict[str, Any]]) -> str:
    """Render flattened rows as a CSV string with sorted, unioned headers."""
    headers: set[str] = set()
    for row in rows:
        headers.update(row.keys())
    fieldnames = sorted(headers)

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        restval="",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def main() -> None:
    records = build_sample_data()

    json_text = to_json_string(records)
    flat_rows = json_to_flat_rows(json_text)
    csv_text = rows_to_csv_string(flat_rows)

    print("=== JSON ===")
    print(json_text)
    print("=== CSV ===")
    print(csv_text, end="")


if __name__ == "__main__":
    main()
