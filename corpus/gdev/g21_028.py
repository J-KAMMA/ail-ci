# task: Encode a list of Python dataclass-like dictionaries generated in a loop and print the JSON Lines format with one object per line.
import json
from dataclasses import dataclass, asdict


@dataclass
class Record:
    id: int
    name: str
    score: float
    tags: list[str]
    active: bool


def build_records(count: int) -> list[Record]:
    records: list[Record] = []
    for i in range(1, count + 1):
        record = Record(
            id=i,
            name=f"item-{i:03d}",
            score=round(i * 1.5 + (i % 3) * 0.25, 2),
            tags=[f"tag{j}" for j in range(i % 4)],
            active=(i % 2 == 0),
        )
        records.append(record)
    return records


def to_json_lines(items: list[dict]) -> list[str]:
    return [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in items]


def main() -> None:
    records = build_records(5)
    dicts = [asdict(r) for r in records]
    for line in to_json_lines(dicts):
        print(line)


if __name__ == "__main__":
    main()
