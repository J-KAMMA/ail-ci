# task: Write a generator-based tokenizer that splits a fixed arithmetic expression string into number and operator tokens and print the tokens.
from typing import Iterator


def tokenize(expression: str) -> Iterator[str]:
    """Yield number and operator tokens from an arithmetic expression."""
    i = 0
    n = len(expression)
    while i < n:
        ch = expression[i]
        if ch.isspace():
            i += 1
        elif ch.isdigit() or ch == ".":
            start = i
            while i < n and (expression[i].isdigit() or expression[i] == "."):
                i += 1
            yield expression[start:i]
        elif ch in "+-*/%()^":
            yield ch
            i += 1
        else:
            raise ValueError(f"Unexpected character {ch!r} at position {i}")


def main() -> None:
    expression = "3.5 + 42 * (7 - 2.25) / 5 % 3 ^ 2"
    for token in tokenize(expression):
        print(token)


if __name__ == "__main__":
    main()
