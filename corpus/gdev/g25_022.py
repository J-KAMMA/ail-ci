# task: Use enum.Enum with a lookup dictionary to map color names to hexadecimal codes and print the codes for a fixed list of names.
from enum import Enum


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    YELLOW = "yellow"
    BLACK = "black"
    WHITE = "white"
    ORANGE = "orange"
    PURPLE = "purple"


HEX_CODES: dict[Color, str] = {
    Color.RED: "#FF0000",
    Color.GREEN: "#008000",
    Color.BLUE: "#0000FF",
    Color.YELLOW: "#FFFF00",
    Color.BLACK: "#000000",
    Color.WHITE: "#FFFFFF",
    Color.ORANGE: "#FFA500",
    Color.PURPLE: "#800080",
}

COLOR_NAMES: list[str] = [
    "red",
    "green",
    "blue",
    "yellow",
    "black",
    "white",
    "orange",
    "purple",
    "magenta",
]


def lookup_hex(name: str) -> str | None:
    """Return the hex code for a color name, or None if unknown."""
    for color in Color:
        if color.value == name.lower():
            return HEX_CODES[color]
    return None


def main() -> None:
    for name in COLOR_NAMES:
        code = lookup_hex(name)
        if code is None:
            print(f"{name}: no hex code found")
        else:
            print(f"{name}: {code}")


if __name__ == "__main__":
    main()
