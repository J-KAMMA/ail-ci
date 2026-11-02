# task: Write a script that centers several hardcoded titles within a 50-character bordered box and prints them.
"""Print several hardcoded titles, each centered inside a 50-character bordered box."""

BOX_WIDTH: int = 50
BORDER_CHAR: str = "*"
TITLES: tuple[str, ...] = (
    "Quarterly Report",
    "Sales Summary",
    "Regional Highlights",
    "Next Steps",
)


def build_box(titles: tuple[str, ...], width: int = BOX_WIDTH) -> list[str]:
    """Return the lines of a bordered box with each title centered on its own row."""
    inner_width: int = width - 2
    border: str = BORDER_CHAR * width
    blank_row: str = BORDER_CHAR + " " * inner_width + BORDER_CHAR

    lines: list[str] = [border, blank_row]
    for title in titles:
        text: str = title[:inner_width]
        lines.append(BORDER_CHAR + text.center(inner_width) + BORDER_CHAR)
        lines.append(blank_row)
    lines.append(border)
    return lines


def main() -> None:
    for line in build_box(TITLES):
        print(line)


if __name__ == "__main__":
    main()
