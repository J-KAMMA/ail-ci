# task: Write a script that uses re.match to parse hardcoded Markdown-style headings and prints each heading's level and title.
import re
from typing import Optional


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")

HARDCODED_LINES: list[str] = [
    "# Introduction",
    "## Background",
    "### Historical Context",
    "Some ordinary paragraph text that is not a heading.",
    "#### Deep Detail ####",
    "##Not A Heading Without Space",
    "##  Extra Spaces Around Title   ",
    "##### Level Five",
    "###### Level Six",
    "####### Too Many Hashes",
    "## Closing Thoughts ##",
]


def parse_heading(line: str) -> Optional[tuple[int, str]]:
    """Return (level, title) if the line is a Markdown heading, else None."""
    match = HEADING_PATTERN.match(line)
    if match is None:
        return None
    level = len(match.group(1))
    title = match.group(2).strip()
    return level, title


def main() -> None:
    for line_number, line in enumerate(HARDCODED_LINES, start=1):
        result = parse_heading(line)
        if result is None:
            continue
        level, title = result
        print(f"Line {line_number}: level={level} title={title!r}")


if __name__ == "__main__":
    main()
