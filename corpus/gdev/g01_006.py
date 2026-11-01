# task: Parse embedded key=value pairs where values may be double-quoted and contain spaces, then print each pair in a normalized form.
from __future__ import annotations


SAMPLE_TEXT: str = r'''
  name="John Smith"   age=42  city="New York"
  empty=""  path=C:\tmp  note="say \"hi\" now"
  flag=on   bare_token   orphan=   title="Dr. \\ Who"
  tail="unterminated value here
'''


def skip_whitespace(text: str, index: int) -> int:
    """Return the index of the first non-whitespace character at or after index."""
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def parse_pairs(text: str) -> list[tuple[str, str]]:
    """Parse key=value pairs where values may be double-quoted with spaces.

    Inside quotes, a backslash escapes the next character. A token without
    an '=' is ignored. An unterminated quote consumes the rest of the text.
    """
    pairs: list[tuple[str, str]] = []
    length = len(text)
    i = 0

    while True:
        i = skip_whitespace(text, i)
        if i >= length:
            break

        key_start = i
        while i < length and text[i] != "=" and not text[i].isspace():
            i += 1
        key = text[key_start:i]

        if i >= length or text[i] != "=":
            # Bare token with no '=': skip it. Progress is guaranteed because
            # the token contains at least one non-space character.
            continue

        i += 1  # consume '='

        if i < length and text[i] == '"':
            i += 1  # consume opening quote
            chars: list[str] = []
            while i < length and text[i] != '"':
                if text[i] == "\\" and i + 1 < length:
                    i += 1
                chars.append(text[i])
                i += 1
            i += 1  # consume closing quote (harmless past end)
            value = "".join(chars)
        else:
            value_start = i
            while i < length and not text[i].isspace():
                i += 1
            value = text[value_start:i]

        if key:
            pairs.append((key, value))

    return pairs


def format_value(value: str) -> str:
    """Return a normalized representation of a value.

    Plain values are left bare. Values that are empty or contain whitespace,
    '=', '"', or a backslash are double-quoted with those characters escaped.
    """
    needs_quotes = not value or any(c.isspace() or c in '="\\' for c in value)
    if not needs_quotes:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def format_pair(key: str, value: str) -> str:
    return f"{key}={format_value(value)}"


def main() -> None:
    pairs = parse_pairs(SAMPLE_TEXT)
    print(f"Parsed {len(pairs)} pair(s):")
    for index, (key, value) in enumerate(pairs, start=1):
        print(f"{index:>2}. {format_pair(key, value)}")


if __name__ == "__main__":
    main()
