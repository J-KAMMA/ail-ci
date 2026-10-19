from __future__ import annotations

import sys


class ParseError(ValueError):
    """Raised when an expression is malformed."""


class Parser:
    """Recursive descent parser and evaluator for integer arithmetic expressions.

    Grammar:
        expr   := term (('+' | '-') term)*
        term   := factor (('*' | '/') factor)*
        factor := ('+' | '-') factor | NUMBER | '(' expr ')'
    """

    def __init__(self, text: str) -> None:
        self.tokens: list[str] = self._tokenize(text)
        self.pos: int = 0

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        tokens: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch.isspace():
                i += 1
            elif ch.isdigit():
                j = i
                while j < n and text[j].isdigit():
                    j += 1
                tokens.append(text[i:j])
                i = j
            elif ch in "+-*/()":
                tokens.append(ch)
                i += 1
            else:
                raise ParseError(f"unexpected character {ch!r}")
        return tokens

    def _peek(self) -> str | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _advance(self) -> str:
        tok = self._peek()
        if tok is None:
            raise ParseError("unexpected end of input")
        self.pos += 1
        return tok

    def parse(self) -> int | float:
        value = self._expr()
        if self._peek() is not None:
            raise ParseError("trailing tokens")
        return value

    def _expr(self) -> int | float:
        value = self._term()
        while self._peek() in ("+", "-"):
            op = self._advance()
            rhs = self._term()
            value = value + rhs if op == "+" else value - rhs
        return value

    def _term(self) -> int | float:
        value = self._factor()
        while self._peek() in ("*", "/"):
            op = self._advance()
            rhs = self._factor()
            if op == "*":
                value = value * rhs
            else:
                value = value / rhs
        return value

    def _factor(self) -> int | float:
        tok = self._peek()
        if tok == "-":
            self._advance()
            return -self._factor()
        if tok == "+":
            self._advance()
            return self._factor()
        if tok == "(":
            self._advance()
            value = self._expr()
            if self._peek() != ")":
                raise ParseError("expected ')'")
            self._advance()
            return value
        if tok is not None and tok.isdigit():
            self._advance()
            return int(tok)
        raise ParseError(f"unexpected token {tok!r}")


def evaluate(line: str) -> str:
    try:
        result = Parser(line).parse()
    except ZeroDivisionError:
        return "error"
    except (ParseError, OverflowError, ValueError):
        return "error"
    return repr(result)


def main() -> None:
    out: list[str] = []
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        out.append(evaluate(line))
    if out:
        sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
