# task: Parse embedded fixed-width records using fixed column slice positions and print each record as a tuple.
from typing import NamedTuple


class Field(NamedTuple):
    name: str
    start: int
    end: int


FIELDS: tuple[Field, ...] = (
    Field("id", 0, 5),
    Field("name", 5, 25),
    Field("dept", 25, 33),
    Field("salary", 33, 41),
    Field("active", 41, 42),
)

RECORDS: tuple[str, ...] = (
    "00001Alice Johnson       ENGINEER","",
)


def parse_line(line: str, fields: tuple[Field, ...]) -> tuple[str, ...]:
    """Slice a fixed-width line into a tuple of stripped field values."""
    return tuple(line[f.start:f.end].strip() for f in fields)


def main() -> None:
    embedded: tuple[str, ...] = (
        "00001Alice Johnson       ENGINEER  0085000Y",
        "00002Bob Smith           MARKETING 0062500N",
        "00003Carol White         SALES     0071250Y",
        "00004Dan Brown           ENGINEER  0093000Y",
        "00005Eve Davis           HR        0058000N",
    )
    for line in embedded:
        print(parse_line(line, FIELDS))


if __name__ == "__main__":
    main()
