# task: Use a match statement with structural pattern matching on tuples to evaluate a fixed list of simple arithmetic expressions represented as tuples.
from typing import Union

Expr = Union[int, tuple]


def evaluate(expr: Expr) -> int | float:
    """Evaluate an arithmetic expression represented as nested tuples."""
    match expr:
        case int() as value:
            return value
        case ("add", left, right):
            return evaluate(left) + evaluate(right)
        case ("sub", left, right):
            return evaluate(left) - evaluate(right)
        case ("mul", left, right):
            return evaluate(left) * evaluate(right)
        case ("div", left, right):
            divisor = evaluate(right)
            if divisor == 0:
                raise ZeroDivisionError("division by zero in expression")
            return evaluate(left) / divisor
        case ("neg", operand):
            return -evaluate(operand)
        case ("pow", base, exponent):
            return evaluate(base) ** evaluate(exponent)
        case _:
            raise ValueError(f"unsupported expression: {expr!r}")


def to_string(expr: Expr) -> str:
    """Render an expression tuple as a readable infix string."""
    match expr:
        case int() as value:
            return str(value)
        case ("add", left, right):
            return f"({to_string(left)} + {to_string(right)})"
        case ("sub", left, right):
            return f"({to_string(left)} - {to_string(right)})"
        case ("mul", left, right):
            return f"({to_string(left)} * {to_string(right)})"
        case ("div", left, right):
            return f"({to_string(left)} / {to_string(right)})"
        case ("neg", operand):
            return f"(-{to_string(operand)})"
        case ("pow", base, exponent):
            return f"({to_string(base)} ** {to_string(exponent)})"
        case _:
            return repr(expr)


EXPRESSIONS: list[Expr] = [
    ("add", 2, 3),
    ("mul", ("add", 1, 2), ("sub", 10, 4)),
    ("div", 7, 2),
    ("div", 9, ("sub", 3, 3)),
    ("neg", ("pow", 2, 10)),
    ("pow", ("sub", 5, 2), 3),
    ("mod", 5, 2),
    42,
    ("add", ("mul", 3, 3), ("neg", 4)),
]


def main() -> None:
    for index, expr in enumerate(EXPRESSIONS, start=1):
        text = to_string(expr)
        try:
            result = evaluate(expr)
        except ZeroDivisionError as exc:
            print(f"{index}. {text} => error: {exc}")
        except ValueError as exc:
            print(f"{index}. {text} => error: {exc}")
        else:
            print(f"{index}. {text} => {result}")


if __name__ == "__main__":
    main()
