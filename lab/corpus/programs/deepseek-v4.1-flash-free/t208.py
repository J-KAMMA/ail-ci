import sys


def tokenize(expr: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(expr):
        c = expr[i]
        if c.isspace():
            i += 1
        elif c.isdigit():
            j = i
            while j < len(expr) and expr[j].isdigit():
                j += 1
            tokens.append(expr[i:j])
            i = j
        elif c in "+-*/()":
            tokens.append(c)
            i += 1
        else:
            raise ValueError(f"unexpected character: {c!r}")
    return tokens


class Parser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self) -> str:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def parse(self) -> int | float:
        value = self.parse_expr()
        if self.pos != len(self.tokens):
            raise ValueError("trailing tokens")
        return value

    def parse_expr(self) -> int | float:
        value = self.parse_term()
        while self.peek() in ("+", "-"):
            op = self.advance()
            right = self.parse_term()
            value = value + right if op == "+" else value - right
        return value

    def parse_term(self) -> int | float:
        value = self.parse_factor()
        while self.peek() in ("*", "/"):
            op = self.advance()
            right = self.parse_factor()
            if op == "*":
                value = value * right
            else:
                if right == 0:
                    raise ZeroDivisionError
                value = value / right
        return value

    def parse_factor(self) -> int | float:
        token = self.peek()
        if token == "-":
            self.advance()
            return -self.parse_factor()
        if token == "+":
            self.advance()
            return self.parse_factor()
        if token == "(":
            self.advance()
            value = self.parse_expr()
            if self.peek() != ")":
                raise ValueError("missing closing parenthesis")
            self.advance()
            return value
        if token is not None and token.isdigit():
            return int(self.advance())
        raise ValueError("unexpected end of expression")


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            result = Parser(tokenize(line)).parse()
        except ZeroDivisionError:
            print("error")
        except ValueError:
            print("error")
        else:
            print(repr(result))


if __name__ == "__main__":
    main()
