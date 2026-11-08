# task: Write a script that uses re.findall to extract all hexadecimal color codes in #RRGGBB or #RGB form from a hardcoded CSS string and prints them.
import re

CSS_TEXT: str = """
/* Theme colors */
:root {
    --primary: #1a73e8;
    --accent: #F0A;
    --background: #fff;
    --text: #202124;
    --border: #DADCE0;
    --shadow: rgba(0, 0, 0, 0.2);
}

body {
    background-color: #FAFAFA;
    color: var(--text);
    font-family: sans-serif;
}

/* Invalid or non-matching tokens */
.header {
    background: #abcd;
    border-color: #ggg;
    fill: #1234567;
}

a:hover {
    color: #0B57D0;
    outline: 1px solid #3c4;
}

#main-content {
    border: 2px dashed #9AA0A6;
    box-shadow: 0 0 4px #00000033;
}
"""

HEX_COLOR_PATTERN: str = r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b"


def find_hex_colors(text: str) -> list[str]:
    """Return all #RRGGBB or #RGB color codes found in the given text, in order."""
    return re.findall(HEX_COLOR_PATTERN, text)


def main() -> None:
    colors: list[str] = find_hex_colors(CSS_TEXT)
    print(f"Found {len(colors)} hex color codes:")
    for color in colors:
        print(color)


if __name__ == "__main__":
    main()
