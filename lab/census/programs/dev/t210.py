import re
import sys

TOKEN_PATTERN = re.compile(r"\d+|[-+*/()]")
OPERATORS = frozenset("+-*/")


def tokenise(line: str) -> list[str]:
    """Return the integer, operator and parenthesis tokens in a line."""
    return TOKEN_PATTERN.findall(line)


def count_operators(tokens: list[str]) -> int:
    """Count tokens that are arithmetic operators (+, -, *, /)."""
    return sum(1 for token in tokens if token in OPERATORS)


def main() -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        tokens = tokenise(line)
        print(repr(tokens))
        print(count_operators(tokens))


if __name__ == "__main__":
    main()
