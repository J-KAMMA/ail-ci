# task: Write a script that converts a hardcoded list of snake_case identifiers into camelCase and prints each conversion.
from typing import Iterable


SNAKE_CASE_IDENTIFIERS: list[str] = [
    "user_name",
    "first_name",
    "max_retry_count",
    "http_response_code",
    "already_camel",
    "__private_value__",
    "trailing_underscore_",
    "_leading_underscore",
    "multiple__underscores",
    "single",
    "",
    "parse_json_v2_response",
    "x_y_z",
]


def snake_to_camel(identifier: str) -> str:
    """Convert a snake_case identifier to camelCase.

    Leading and trailing underscores are preserved, empty segments
    produced by consecutive underscores are skipped, and the first
    non-empty segment is kept lowercase while later segments have
    their first character uppercased.
    """
    if not identifier:
        return identifier

    stripped = identifier.strip("_")
    if not stripped:
        return identifier

    leading = identifier[: len(identifier) - len(identifier.lstrip("_"))]
    trailing = identifier[len(identifier.rstrip("_")):]

    parts: list[str] = [part for part in stripped.split("_") if part]
    if not parts:
        return identifier

    first, *rest = parts
    camel = first.lower() + "".join(word[:1].upper() + word[1:] for word in rest)
    return f"{leading}{camel}{trailing}"


def convert_all(identifiers: Iterable[str]) -> list[tuple[str, str]]:
    """Return (original, converted) pairs in input order."""
    return [(name, snake_to_camel(name)) for name in identifiers]


def main() -> None:
    for original, converted in convert_all(SNAKE_CASE_IDENTIFIERS):
        display_original = repr(original) if original == "" else original
        print(f"{display_original} -> {converted}")


if __name__ == "__main__":
    main()
