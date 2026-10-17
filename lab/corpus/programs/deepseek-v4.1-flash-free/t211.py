import sys


def evaluate(line: str) -> str:
    stack: list[int] = []
    for token in line.split():
        if token in "+-*":
            if len(stack) < 2:
                return "error"
            b = stack.pop()
            a = stack.pop()
            if token == "+":
                stack.append(a + b)
            elif token == "-":
                stack.append(a - b)
            else:
                stack.append(a * b)
        elif len(token) == 1 and token.isdigit() and token != "0":
            stack.append(int(token))
        else:
            return "error"
    return str(stack[0]) if len(stack) == 1 else "error"


def main() -> None:
    results = [evaluate(line) for line in sys.stdin]
    if results:
        sys.stdout.write("\n".join(results) + "\n")


if __name__ == "__main__":
    main()
