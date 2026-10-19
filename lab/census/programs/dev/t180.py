import json
import sys
from typing import Any


def format_record(record: dict[str, Any]) -> str:
    meta: dict[str, Any] = record["meta"]
    level = meta.get("level")
    note = meta.get("note")
    note_text = "-" if note is None else str(note)
    return f"{record['id']}: level={level} note={note_text}"


def main() -> None:
    data: Any = json.loads(sys.stdin.read())
    records: list[dict[str, Any]] = [
        r for r in data
        if isinstance(r, dict) and isinstance(r.get("meta"), dict)
    ]
    records.sort(key=lambda r: r["id"])
    for record in records:
        print(format_record(record))


if __name__ == "__main__":
    main()
