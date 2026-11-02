# task: Serialize a dictionary with deeply nested lists and print the output with indentation of 2 spaces and sorted keys.
import json
from typing import Any


def build_nested_list(depth: int, width: int) -> list[Any]:
    """Build a deterministic, deeply nested list structure."""
    if depth == 0:
        return [index * index for index in range(width)]
    return [
        {
            "depth": depth,
            "branch": branch,
            "items": build_nested_list(depth - 1, width),
        }
        for branch in range(2)
    ]


def build_document() -> dict[str, Any]:
    """Create a dictionary with deeply nested lists and mixed value types."""
    return {
        "name": "nested-serialization-demo",
        "version": 3,
        "enabled": True,
        "zeta": {
            "notes": None,
            "levels": build_nested_list(depth=4, width=3),
        },
        "alpha": {
            "matrix": [
                [[1, 2], [3, [4, [5, [6]]]]],
                [[], [7, 8, [9, {"inner": ["x", "y"]}]]],
            ],
            "label": "deep",
        },
        "middle": [
            {"b": 2, "a": 1, "c": [3, [4, [5]]]},
            ["plain", "list", ["of", ["strings", ["deep"]]]],
        ],
    }


def serialize(data: dict[str, Any]) -> str:
    """Serialize the dictionary as JSON with 2-space indentation and sorted keys."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)


def main() -> None:
    document: dict[str, Any] = build_document()
    print(serialize(document))


if __name__ == "__main__":
    main()
