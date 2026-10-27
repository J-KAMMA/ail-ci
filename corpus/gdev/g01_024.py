# task: Parse embedded dotted key=value lines such as 'db.host=x' into a nested dictionary and print it as indented JSON.
import json
from typing import Any

EMBEDDED_CONFIG = """
# Application settings
db.host=localhost
db.port=5432
db.name=appdb
db.pool.min=2
db.pool.max=10
server.bind=0.0.0.0
server.port=8080
logging.level=info
logging.handlers.console.enabled=true
logging.handlers.file.path=/var/log/app.log
feature.beta=false
"""


def parse_line(line: str) -> tuple[str, str] | None:
    """Return (dotted_key, value) for a key=value line, or None for blanks/comments."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if "=" not in stripped:
        raise ValueError(f"missing '=' in line: {line!r}")
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key or any(not part for part in key.split(".")):
        raise ValueError(f"invalid dotted key: {line!r}")
    return key, value


def insert_nested(tree: dict[str, Any], dotted_key: str, value: str) -> None:
    """Insert value into tree at the path described by dotted_key."""
    parts = dotted_key.split(".")
    node: dict[str, Any] = tree
    for part in parts[:-1]:
        child = node.setdefault(part, {})
        if not isinstance(child, dict):
            raise ValueError(f"conflict: '{part}' is both a value and a section in {dotted_key!r}")
        node = child
    leaf = parts[-1]
    if leaf in node:
        raise ValueError(f"duplicate or conflicting key: {dotted_key!r}")
    node[leaf] = value


def build_tree(text: str) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for line in text.splitlines():
        parsed = parse_line(line)
        if parsed is None:
            continue
        key, value = parsed
        insert_nested(tree, key, value)
    return tree


def main() -> None:
    tree = build_tree(EMBEDDED_CONFIG)
    print(json.dumps(tree, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
