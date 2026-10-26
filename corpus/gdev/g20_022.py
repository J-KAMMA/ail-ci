# task: Write a script that uses re.sub to convert hardcoded camelCase identifiers into snake_case and prints the converted list.
import re


CAMEL_TO_SNAKE_ACRONYM: re.Pattern[str] = re.compile(r"([A-Z]+)([A-Z][a-z])")
CAMEL_TO_SNAKE_BOUNDARY: re.Pattern[str] = re.compile(r"([a-z0-9])([A-Z])")

IDENTIFIERS: list[str] = [
    "userName",
    "getHTTPResponseCode",
    "parseHTMLDocument",
    "XMLHttpRequest",
    "maxRetryCount",
    "getHTML5Parser",
    "userID",
    "isEnabled2FA",
    "simpleValue",
    "readJSONFile",
    "already_snake",
    "startX",
]


def camel_to_snake(name: str) -> str:
    """Convert a camelCase identifier to snake_case using re.sub."""
    step1: str = CAMEL_TO_SNAKE_ACRONYM.sub(r"\1_\2", name)
    step2: str = CAMEL_TO_SNAKE_BOUNDARY.sub(r"\1_\2", step1)
    return step2.lower()


def convert_all(names: list[str]) -> list[str]:
    """Convert every identifier in the list."""
    return [camel_to_snake(name) for name in names]


def main() -> None:
    converted: list[str] = convert_all(IDENTIFIERS)
    print(converted)


if __name__ == "__main__":
    main()
