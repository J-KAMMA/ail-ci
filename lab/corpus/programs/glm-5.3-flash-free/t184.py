import json
import sys
from typing import Any, Iterator


def flatten(value: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield path, value
        else:
            for key, item in value.items():
                child = f"{path}.{key}" if path else key
                yield from flatten(item, child)
    elif isinstance(value, list):
        if not value:
            yield path, value
        else:
            for index, item in enumerate(value):
                yield from flatten(item, f"{path}[{index}]")
    else:
        yield path, value


def main() -> None:
    data = json.load(sys.stdin)
    for path, value in flatten(data):
        prefix = f"{path} = " if path else ""
        print(f"{prefix}{json.dumps(value)}")


if __name__ == "__main__":
    main()
