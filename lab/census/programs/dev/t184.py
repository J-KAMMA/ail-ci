import json
import sys
from typing import Any


def flatten(value: Any, prefix: str, out: list[str]) -> None:
    """Recursively append 'path = json_value' lines for every leaf and empty container."""
    if isinstance(value, dict):
        if not value:
            out.append(f"{prefix} = {json.dumps(value)}")
            return
        for key, item in value.items():
            child = key if not prefix else f"{prefix}.{key}"
            flatten(item, child, out)
    elif isinstance(value, list):
        if not value:
            out.append(f"{prefix} = {json.dumps(value)}")
            return
        for index, item in enumerate(value):
            flatten(item, f"{prefix}[{index}]", out)
    else:
        out.append(f"{prefix} = {json.dumps(value)}")


def main() -> None:
    text = sys.stdin.read().strip()
    data: Any = json.loads(text)
    lines: list[str] = []
    flatten(data, "", lines)
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
