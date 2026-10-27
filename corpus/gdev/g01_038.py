# task: Parse an embedded Markdown pipe table and print each row's cell values with surrounding whitespace removed.
import re

TABLE_TEXT: str = """
| Name      | Language |  Score  |
|:----------|:--------:|--------:|
|  Alice    |  Python  |   95    |
| Bob       | C++      |88       |
|   Carol   | Go       |  91     |
| Escaped   | a \\| b  |  70     |
"""

SEPARATOR_CELL = re.compile(r"^:?-+:?$")
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


def split_row(line: str) -> list[str]:
    """Split one Markdown pipe-table line into cells, stripping whitespace."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    parts = UNESCAPED_PIPE.split(stripped)
    return [part.strip().replace("\\|", "|") for part in parts]


def is_separator_row(cells: list[str]) -> bool:
    """Return True if every cell matches the Markdown alignment syntax."""
    return bool(cells) and all(SEPARATOR_CELL.match(cell) for cell in cells)


def parse_table(text: str) -> list[list[str]]:
    """Parse a Markdown pipe table, dropping blank lines and the separator row."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        cells = split_row(line)
        if is_separator_row(cells):
            continue
        rows.append(cells)
    return rows


def main() -> None:
    rows: list[list[str]] = parse_table(TABLE_TEXT)
    for row in rows:
        print(" | ".join(row))


if __name__ == "__main__":
    main()
