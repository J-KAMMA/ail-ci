import re
import sys

TOKEN_RE = re.compile(r"\d+|[()+\-*/]")


def main() -> None:
    for line in sys.stdin:
        stripped = line.strip()
        if not stripped:
            continue
        tokens = TOKEN_RE.findall(stripped)
        operator_count = sum(1 for token in tokens if token in "+-*/")
        print(repr(tokens), operator_count)


if __name__ == "__main__":
    main()
