# task: Serialize a nested dictionary and then compute and print its SHA-256 hash of the sorted-key JSON representation.
import hashlib
import json
from typing import Any


def build_nested_data() -> dict[str, Any]:
    """Construct a fixed nested dictionary to serialize."""
    return {
        "name": "example",
        "version": 3,
        "enabled": True,
        "ratio": 0.75,
        "tags": ["alpha", "beta", "gamma"],
        "owner": {
            "id": 42,
            "email": "owner@example.com",
            "roles": {
                "admin": True,
                "editor": False,
                "viewer": True,
            },
        },
        "settings": {
            "retries": 5,
            "timeout_seconds": 30.5,
            "endpoints": [
                {"url": "https://a.example.com", "weight": 1},
                {"url": "https://b.example.com", "weight": 2},
            ],
            "limits": {
                "max_items": 1000,
                "max_size_kb": None,
            },
        },
    }


def serialize_sorted(data: dict[str, Any]) -> str:
    """Return a canonical JSON string with sorted keys and compact separators."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_hex(text: str) -> str:
    """Compute the SHA-256 hex digest of the UTF-8 encoded text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    data = build_nested_data()
    serialized = serialize_sorted(data)
    digest = sha256_hex(serialized)
    print(serialized)
    print(digest)


if __name__ == "__main__":
    main()
