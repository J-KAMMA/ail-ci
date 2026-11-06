# task: Parse a multi-line key=value configuration string and raise a custom error that reports the line number of the first malformed entry.
import re
from typing import Final

KEY_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-]*")

GOOD_CONFIG: Final[str] = """\
# Application settings
app.name = inventory-service
app.debug = false

db.host = localhost
db.port = 5432
db.user = svc_inventory
"""

BAD_CONFIG: Final[str] = """\
# Application settings
app.name = inventory-service
app.debug = false
db.host localhost
db.port = 5432
"""

DUPLICATE_CONFIG: Final[str] = """\
alpha = 1
beta = 2
alpha = 3
"""


class ConfigParseError(ValueError):
    """Raised when a configuration line is malformed."""

    def __init__(self, line_number: int, line: str, reason: str) -> None:
        super().__init__(f"line {line_number}: {reason}: {line!r}")
        self.line_number: int = line_number
        self.line: str = line
        self.reason: str = reason


def parse_config(text: str) -> dict[str, str]:
    """Parse key=value lines, raising ConfigParseError on the first malformed entry.

    Blank lines and lines starting with '#' are ignored. Line numbers are 1-based.
    """
    result: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        key_part, separator, value_part = stripped.partition("=")
        if not separator:
            raise ConfigParseError(line_number, raw_line, "missing '='")

        key = key_part.strip()
        if not KEY_PATTERN.fullmatch(key):
            raise ConfigParseError(line_number, raw_line, "invalid key")

        if key in result:
            raise ConfigParseError(line_number, raw_line, f"duplicate key {key!r}")

        result[key] = value_part.strip()
    return result


def main() -> None:
    print("Parsing GOOD_CONFIG:")
    settings = parse_config(GOOD_CONFIG)
    for key in sorted(settings):
        print(f"  {key} -> {settings[key]}")

    print()
    for label, text in (("BAD_CONFIG", BAD_CONFIG), ("DUPLICATE_CONFIG", DUPLICATE_CONFIG)):
        print(f"Parsing {label}:")
        try:
            parse_config(text)
        except ConfigParseError as err:
            print(f"  error at line {err.line_number}: {err.reason}")
            print(f"  offending text: {err.line!r}")
        else:
            print("  no errors found")
        print()


if __name__ == "__main__":
    main()
