import sys


def execute(stack: list[str], line: str) -> None:
    tokens = line.split()
    if not tokens:
        return
    op, args = tokens[0], tokens[1:]
    if op == "push" and args:
        stack.append(args[0])
    elif op == "pop" and not args:
        if stack:
            stack.pop()
    elif op in ("size", "peek") and not args:
        pass


def main() -> None:
    stack: list[str] = []
    for line in sys.stdin:
        execute(stack, line)
    for value in stack:
        print(value)


if __name__ == "__main__":
    main()
