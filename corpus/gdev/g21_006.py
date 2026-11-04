# task: Parse a JSON string containing Unicode escape sequences and print the decoded text with ensure_ascii=False output.
import json
import sys


# A raw string keeps the backslashes so the JSON parser sees the Unicode escapes.
SAMPLE_JSON: str = (
    r'{"greeting": "\u0048\u0065\u006c\u006c\u006f", '
    r'"chinese": "\u4f60\u597d", '
    r'"accented": "caf\u00e9", '
    r'"emoji": "\ud83d\ude00", '
    r'"quote": "She said \u201cHi\u201d"}'
)


def decode_json_text(text: str) -> object:
    """Parse a JSON document, decoding any \\uXXXX escape sequences."""
    return json.loads(text)


def print_value(key: str, value: object) -> None:
    """Print a decoded string value together with its code point count."""
    if isinstance(value, str):
        print(f"{key}: {value} (length={len(value)})")
    else:
        print(f"{key}: {value!r}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    data: object = decode_json_text(SAMPLE_JSON)

    print("Decoded values:")
    if isinstance(data, dict):
        for key, value in data.items():
            print_value(str(key), value)

    print()
    print("Re-serialized with ensure_ascii=False:")
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
