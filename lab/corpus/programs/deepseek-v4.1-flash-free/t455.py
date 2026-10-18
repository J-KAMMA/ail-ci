import re
import sys
from dataclasses import dataclass

TOKEN_SPECS: list[tuple[str, str]] = [
    ("NUMBER", r"\d+"),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("STAR", r"\*"),
    ("SLASH", r"/"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("SPACE", r"\s+"),
]

COMPILED_SPECS: list[tuple[str, re.Pattern[str]]] = [
    (name, re.compile(pattern)) for name, pattern in TOKEN_SPECS
]


@dataclass
class Token:
    type: str
    value: str


class Tokenizer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self._peeked: Token | None = None
        self._peeked_pos = 0

    def _scan(self) -> Token:
        while self.pos < len(self.text):
            for name, regex in COMPILED_SPECS:
                match = regex.match(self.text, self.pos)
                if match is not None:
                    value = match.group(0)
                    self.pos = match.end()
                    if name == "SPACE":
                        break
                    return Token(name, value)
            else:
                raise ValueError(
                    f"Unexpected character {self.text[self.pos]!r} at position {self.pos}"
                )
        return Token("EOF", "")

    def peek(self) -> Token:
        if self._peeked is None:
            saved = self.pos
            self._peeked = self._scan()
            self._peeked_pos = self.pos
            self.pos = saved
        return self._peeked

    def next(self) -> Token:
        token = self.peek()
        self.pos = self._peeked_pos
        self._peeked = None
        return token


def tokenize_line(line: str) -> list[Token]:
    tokenizer = Tokenizer(line)
    tokens: list[Token] = []
    while True:
        token = tokenizer.next()
        if token.type == "EOF":
            break
        tokens.append(token)
    return tokens


def main() -> None:
    for line in sys.stdin:
        line = line.rstrip("\n")
        for token in tokenize_line(line):
            print(f"{token.type} {token.value}")


if __name__ == "__main__":
    main()
