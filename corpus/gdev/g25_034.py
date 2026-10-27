# task: Write a state machine that simulates a simple lexer for arithmetic expressions and prints each token type for a fixed input string.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    NUMBER = auto()
    IDENT = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    CARET = auto()
    LPAREN = auto()
    RPAREN = auto()
    END = auto()
    ERROR = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenType
    text: str
    position: int


class State(Enum):
    START = auto()
    INT = auto()
    FRACTION_START = auto()
    FRACTION = auto()
    IDENT = auto()
    DONE = auto()
    ERROR = auto()


SINGLE_CHAR_TOKENS: dict[str, TokenType] = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "^": TokenType.CARET,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
}


class Lexer:
    """A state-machine lexer for simple arithmetic expressions."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.pos = 0
        self.state = State.START
        self.start = 0
        self.tokens: list[Token] = []

    def _peek(self) -> str:
        if self.pos < len(self.source):
            return self.source[self.pos]
        return ""

    def _emit(self, kind: TokenType) -> None:
        text = self.source[self.start:self.pos]
        self.tokens.append(Token(kind, text, self.start))

    def run(self) -> list[Token]:
        while self.state is not State.DONE:
            handler = {
                State.START: self._state_start,
                State.INT: self._state_int,
                State.FRACTION_START: self._state_fraction_start,
                State.FRACTION: self._state_fraction,
                State.IDENT: self._state_ident,
                State.ERROR: self._state_error,
            }[self.state]
            handler()
        self.tokens.append(Token(TokenType.END, "", len(self.source)))
        return self.tokens

    def _state_start(self) -> None:
        ch = self._peek()
        if ch == "":
            self.state = State.DONE
        elif ch.isspace():
            self.pos += 1
            self.start = self.pos
        elif ch.isdigit():
            self.start = self.pos
            self.pos += 1
            self.state = State.INT
        elif ch.isalpha() or ch == "_":
            self.start = self.pos
            self.pos += 1
            self.state = State.IDENT
        elif ch == ".":
            self.start = self.pos
            self.pos += 1
            self.state = State.FRACTION_START
        elif ch in SINGLE_CHAR_TOKENS:
            self.start = self.pos
            self.pos += 1
            self._emit(SINGLE_CHAR_TOKENS[ch])
            self.start = self.pos
        else:
            self.start = self.pos
            self.pos += 1
            self.state = State.ERROR

    def _state_int(self) -> None:
        ch = self._peek()
        if ch != "" and ch.isdigit():
            self.pos += 1
        elif ch == ".":
            self.pos += 1
            self.state = State.FRACTION
        else:
            self._emit(TokenType.NUMBER)
            self.start = self.pos
            self.state = State.START

    def _state_fraction_start(self) -> None:
        ch = self._peek()
        if ch != "" and ch.isdigit():
            self.pos += 1
            self.state = State.FRACTION
        else:
            self.state = State.ERROR

    def _state_fraction(self) -> None:
        ch = self._peek()
        if ch != "" and ch.isdigit():
            self.pos += 1
        else:
            self._emit(TokenType.NUMBER)
            self.start = self.pos
            self.state = State.START

    def _state_ident(self) -> None:
        ch = self._peek()
        if ch != "" and (ch.isalnum() or ch == "_"):
            self.pos += 1
        else:
            self._emit(TokenType.IDENT)
            self.start = self.pos
            self.state = State.START

    def _state_error(self) -> None:
        self._emit(TokenType.ERROR)
        self.start = self.pos
        self.state = State.DONE


def main() -> None:
    expression = "x1 = (3.25 + 40) * rate_2 ^ 2 - .5 / 7 $ 9.x"
    print(f"Input: {expression!r}")
    print()
    lexer = Lexer(expression)
    for token in lexer.run():
        print(f"{token.position:>3}  {token.kind.name:<8} {token.text!r}")


if __name__ == "__main__":
    main()
