# task: Create a JSON schema-like description dictionary by hand, serialize it, and print the number of top-level properties.
import json
from typing import Any


def build_schema() -> dict[str, Any]:
    """Build a JSON schema-like description dictionary by hand."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "User",
        "description": "A simple user record",
        "type": "object",
        "properties": {
            "id": {
                "type": "integer",
                "minimum": 1,
            },
            "name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 100,
            },
            "email": {
                "type": "string",
                "format": "email",
            },
            "age": {
                "type": "integer",
                "minimum": 0,
                "maximum": 150,
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True,
            },
        },
        "required": ["id", "name", "email"],
        "additionalProperties": False,
    }


def count_top_level_properties(schema: dict[str, Any]) -> int:
    """Return the number of top-level properties declared in the schema."""
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return 0
    return len(properties)


def main() -> None:
    schema = build_schema()
    serialized = json.dumps(schema, indent=2, sort_keys=True)
    print(serialized)
    count = count_top_level_properties(json.loads(serialized))
    print(f"Number of top-level properties: {count}")


if __name__ == "__main__":
    main()
