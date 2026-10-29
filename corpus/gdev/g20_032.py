# task: Write a script that uses re.compile to build a reusable pattern that matches hardcoded North American ZIP codes including ZIP+4 and prints the matches.
import re
from typing import Final

ZIP_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""
    (?<![\d-])            # not preceded by a digit or hyphen
    (?P<zip5>\d{5})       # 5-digit ZIP code
    (?:-(?P<plus4>\d{4}))?  # optional +4 extension
    (?![\d-])             # not followed by a digit or hyphen
    """,
    re.VERBOSE,
)

SAMPLE_TEXT: Final[str] = """\
Shipping addresses:
  Acme Corp, 100 Main St, Springfield, IL 62704
  Widget Works, 42 Oak Ave, Cambridge, MA 02139-4307
  Parcel depot: 90210-1234 (Beverly Hills, CA)
  Invalid long number: 123456 should not match
  Partial: 1234-5678 should not match
  Phone-like 555-1234 should not match
  Office ZIP+4 at 10001-0001 and plain 73301.
  Bad trailing digits 4455566 should not match
"""


def find_zip_codes(text: str) -> list[re.Match[str]]:
    """Return all ZIP / ZIP+4 matches found in the given text."""
    return list(ZIP_PATTERN.finditer(text))


def main() -> None:
    matches = find_zip_codes(SAMPLE_TEXT)
    print(f"Pattern: {ZIP_PATTERN.pattern.strip()}")
    print(f"Found {len(matches)} ZIP code(s):")
    for index, match in enumerate(matches, start=1):
        zip5 = match.group("zip5")
        plus4 = match.group("plus4")
        kind = "ZIP+4" if plus4 is not None else "ZIP"
        full = match.group(0)
        print(f"{index:2d}. {full:<10} kind={kind:<5} "
              f"base={zip5} plus4={plus4 if plus4 is not None else '-'} "
              f"at={match.start()}-{match.end()}")


if __name__ == "__main__":
    main()
