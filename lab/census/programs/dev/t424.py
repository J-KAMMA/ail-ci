import sys


def process_line(line: str) -> str:
    """Return the output text for one input line."""
    try:
        value = int(line)
        quotient = 100 / value
    except ZeroDivisionError:
        return "zero"
    except ValueError:
        return "bad"
    return f"{quotient:.2f}"


def main() -> None:
    data = sys.stdin.read().splitlines()
    for line in data:
        print(process_line(line))


if __name__ == "__main__":
    main()
