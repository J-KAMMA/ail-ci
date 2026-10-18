import json
import sys
from typing import Any


def load_records(text: str) -> list[dict[str, Any]]:
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("expected a JSON array")
    return data


def active_names(records: list[dict[str, Any]]) -> list[str]:
    return sorted(record["name"] for record in records if record["active"])


def average_score(records: list[dict[str, Any]]) -> float:
    if not records:
        return 0.0
    return sum(record["score"] for record in records) / len(records)


def main() -> None:
    text = sys.stdin.read().strip()
    records = load_records(text)

    for name in active_names(records):
        print(name)
    print(f"{average_score(records):.2f}")


if __name__ == "__main__":
    main()
