# task: Build a JSON patch-style list of operations from a hardcoded before and after dictionary and print the operations.
from __future__ import annotations

import json
from typing import Any


def escape_pointer_token(token: str) -> str:
    """Escape a single reference token per RFC 6901 (JSON Pointer)."""
    return token.replace("~", "~0").replace("/", "~1")


def make_patch(before: Any, after: Any, path: str = "", ops: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Recursively build RFC 6902-style JSON Patch operations turning `before` into `after`."""
    if ops is None:
        ops = []

    if isinstance(before, dict) and isinstance(after, dict):
        # Sort by string form so the order is deterministic regardless of set/dict internals.
        all_keys = sorted(set(before) | set(after), key=str)
        for key in all_keys:
            child_path = f"{path}/{escape_pointer_token(str(key))}"
            if key not in after:
                ops.append({"op": "remove", "path": child_path})
            elif key not in before:
                ops.append({"op": "add", "path": child_path, "value": after[key]})
            else:
                make_patch(before[key], after[key], child_path, ops)

    elif isinstance(before, list) and isinstance(after, list):
        common = min(len(before), len(after))
        for i in range(common):
            make_patch(before[i], after[i], f"{path}/{i}", ops)
        # Remove trailing elements from the end so earlier indices stay valid.
        for i in range(len(before) - 1, common - 1, -1):
            ops.append({"op": "remove", "path": f"{path}/{i}"})
        # Append new elements in order; each index equals the current length.
        for i in range(common, len(after)):
            ops.append({"op": "add", "path": f"{path}/{i}", "value": after[i]})

    elif type(before) is not type(after) or before != after:
        ops.append({"op": "replace", "path": path, "value": after})

    return ops


def main() -> None:
    before: dict[str, Any] = {
        "name": "Widget",
        "version": 1,
        "enabled": True,
        "tags": ["alpha", "beta", "gamma"],
        "settings": {
            "timeout": 30,
            "retries": 3,
            "mode": "fast",
        },
        "path/with/slash": "old",
        "tilde~key": 10,
        "obsolete": "remove me",
        "count": 5,
    }

    after: dict[str, Any] = {
        "name": "Widget",
        "version": 2,
        "enabled": 1,
        "tags": ["alpha", "delta"],
        "settings": {
            "timeout": 45,
            "retries": 3,
            "mode": "fast",
            "verbose": False,
        },
        "path/with/slash": "new",
        "tilde~key": 10,
        "count": 5,
        "added": {"nested": [1, 2]},
    }

    operations = make_patch(before, after)
    print(json.dumps(operations, indent=2))


if __name__ == "__main__":
    main()
