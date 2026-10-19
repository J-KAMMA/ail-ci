import sys


def parse_line(line: str) -> set[int]:
    return {int(token) for token in line.split()}


def format_set(values: set[int]) -> str:
    return " ".join(str(v) for v in sorted(values))


def main() -> None:
    lines = sys.stdin.read().splitlines()
    while len(lines) < 2:
        lines.append("")

    first = parse_line(lines[0])
    second = parse_line(lines[1])

    union = first | second
    intersection = first & second
    symmetric_difference = first ^ second
    only_first = first - second

    print(format_set(union))
    print(format_set(intersection))
    print(format_set(symmetric_difference))
    print(format_set(only_first))


if __name__ == "__main__":
    main()
