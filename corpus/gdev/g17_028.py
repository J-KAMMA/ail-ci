# task: Filter a list of dictionary records to keep only those containing all required keys, using all() inside filter.
from typing import Any


def has_all_required_keys(record: dict[str, Any], required: tuple[str, ...]) -> bool:
    """Return True if the record contains every required key."""
    return all(key in record for key in required)


def filter_records(records: list[dict[str, Any]], required: tuple[str, ...]) -> list[dict[str, Any]]:
    """Keep only the records that contain all required keys."""
    return list(filter(lambda rec: all(key in rec for key in required), records))


def main() -> None:
    required_keys: tuple[str, ...] = ("id", "name", "email")

    records: list[dict[str, Any]] = [
        {"id": 1, "name": "Alice", "email": "alice@example.com", "age": 30},
        {"id": 2, "name": "Bob", "email": "bob@example.com"},
        {"id": 3, "name": "Carol"},
        {"id": 4, "name": "Dave", "email": "dave@example.com", "role": "admin"},
        {"name": "Eve", "email": "eve@example.com"},
        {"id": 6, "name": "Frank", "email": None},
        {},
        {"id": 8, "name": "Grace", "email": "grace@example.com", "active": True},
    ]

    print(f"Required keys: {', '.join(required_keys)}")
    print(f"Total records: {len(records)}")

    kept = filter_records(records, required_keys)

    print(f"Records with all required keys: {len(kept)}")
    for index, rec in enumerate(kept, start=1):
        print(f"{index}. {rec}")

    dropped = [rec for rec in records if not has_all_required_keys(rec, required_keys)]
    print(f"Records dropped: {len(dropped)}")
    for index, rec in enumerate(dropped, start=1):
        missing = [key for key in required_keys if key not in rec]
        print(f"{index}. missing {', '.join(missing)} in {rec}")


if __name__ == "__main__":
    main()
