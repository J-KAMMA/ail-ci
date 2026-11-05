# task: Parse embedded key=value records separated by blank lines and print the record count along with the fields of the largest record.
from __future__ import annotations

EMBEDDED_DATA: str = """\
name=alpha
host=server1
port=8080
mode=prod

id=beta
owner=alice
size=3

name=gamma
host=server2
port=9090
mode=dev
level=high
region=eu

name=delta
status=ok
"""


def parse_records(text: str) -> list[dict[str, str]]:
    """Split text into blank-line-separated blocks and parse key=value pairs."""
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue  # ignore lines without '='
        key = key.strip()
        if key:
            current[key] = value.strip()

    if current:
        records.append(current)
    return records


def largest_record_index(records: list[dict[str, str]]) -> int | None:
    """Return the index of the record with the most fields (first one wins ties)."""
    if not records:
        return None
    best_index = 0
    best_size = len(records[0])
    for index, record in enumerate(records[1:], start=1):
        if len(record) > best_size:
            best_index = index
            best_size = len(record)
    return best_index


def main() -> None:
    records = parse_records(EMBEDDED_DATA)
    print(f"Record count: {len(records)}")

    idx = largest_record_index(records)
    if idx is None:
        print("No records found.")
        return

    largest = records[idx]
    print(f"Largest record: #{idx + 1} with {len(largest)} fields")
    for key, value in largest.items():
        print(f"  {key} = {value}")


if __name__ == "__main__":
    main()
