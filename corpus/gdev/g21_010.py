# task: Parse a hardcoded JSON document and recursively count the total number of leaf values it contains.
import json
from collections import Counter
from typing import Any

JSON_DOCUMENT: str = """
{
    "name": "inventory",
    "version": 3,
    "active": true,
    "owner": null,
    "tags": ["alpha", "beta", "gamma"],
    "empty_list": [],
    "empty_object": {},
    "warehouses": [
        {
            "id": "WH-01",
            "location": {"city": "Lisbon", "country": "PT", "coords": [38.72, -9.14]},
            "stock": [
                {"sku": "A-100", "qty": 42, "price": 3.5, "discontinued": false},
                {"sku": "B-220", "qty": 0, "price": 12.0, "notes": null}
            ]
        },
        {
            "id": "WH-02",
            "location": {"city": "Oslo", "country": "NO", "coords": [59.91, 10.75]},
            "stock": [],
            "manager": {"name": "Ingrid", "contact": {"email": "ingrid@example.com", "phone": null}}
        }
    ],
    "metadata": {
        "generated_by": "static-fixture",
        "checksums": [[1, 2], [3, [4, 5, [6]]]],
        "flags": {"audited": true, "archived": false, "levels": {}}
    }
}
"""


def count_leaves(node: Any) -> int:
    """Recursively count leaf values (non-container JSON values).

    Empty dicts and lists contribute zero leaves.
    """
    if isinstance(node, dict):
        return sum(count_leaves(value) for value in node.values())
    if isinstance(node, list):
        return sum(count_leaves(item) for item in node)
    return 1


def count_leaves_by_type(node: Any, counts: Counter[str]) -> None:
    """Accumulate leaf counts keyed by their JSON type name."""
    if isinstance(node, dict):
        for value in node.values():
            count_leaves_by_type(value, counts)
    elif isinstance(node, list):
        for item in node:
            count_leaves_by_type(item, counts)
    else:
        if node is None:
            counts["null"] += 1
        elif isinstance(node, bool):
            counts["boolean"] += 1
        elif isinstance(node, (int, float)):
            counts["number"] += 1
        elif isinstance(node, str):
            counts["string"] += 1
        else:
            counts["other"] += 1


def main() -> None:
    document: Any = json.loads(JSON_DOCUMENT)

    total: int = count_leaves(document)
    print(f"Total leaf values: {total}")

    type_counts: Counter[str] = Counter()
    count_leaves_by_type(document, type_counts)

    print("Breakdown by type:")
    for type_name in sorted(type_counts):
        print(f"  {type_name}: {type_counts[type_name]}")


if __name__ == "__main__":
    main()
