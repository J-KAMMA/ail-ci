# task: Write a script that uses named groups in re.finditer to extract key=value pairs from a hardcoded configuration string into a dictionary.
import re
from typing import Dict

CONFIG_TEXT: str = """
# Application configuration
host = example.com
port=8080
debug = true
timeout= 30
name = "My Service"
retries=5
# comment line should be ignored
mode = 'production'
empty =
"""

PAIR_PATTERN: re.Pattern[str] = re.compile(
    r"""
    ^[ \t]*                          # optional leading whitespace
    (?P<key>[A-Za-z_][A-Za-z0-9_.-]*)  # key name
    [ \t]*=[ \t]*                    # equals sign with optional spaces
    (?P<value>
        "(?P<dq>[^"\n]*)"            # double-quoted value
        | '(?P<sq>[^'\n]*)'          # single-quoted value
        | (?P<bare>[^\n#]*?)         # bare value, trailing spaces trimmed below
    )
    [ \t]*(?:\#[^\n]*)?$             # optional trailing spaces/comment
    """,
    re.VERBOSE | re.MULTILINE,
)


def parse_config(text: str) -> Dict[str, str]:
    """Extract key=value pairs from configuration text using named groups."""
    result: Dict[str, str] = {}
    for match in PAIR_PATTERN.finditer(text):
        key: str = match.group("key")
        if match.group("dq") is not None:
            value = match.group("dq")
        elif match.group("sq") is not None:
            value = match.group("sq")
        else:
            value = (match.group("bare") or "").strip()
        result[key] = value
    return result


def main() -> None:
    config: Dict[str, str] = parse_config(CONFIG_TEXT)
    for key in sorted(config):
        print(f"{key}: {config[key]!r}")
    print(f"Total pairs: {len(config)}")


if __name__ == "__main__":
    main()
