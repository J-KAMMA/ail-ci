import heapq
import sys


def parse_line(line: str) -> list[int]:
    return [int(token) for token in line.split()]


def main() -> None:
    lines: list[str] = sys.stdin.read().splitlines()
    while len(lines) < 2:
        lines.append("")

    first: list[int] = sorted(parse_line(lines[0]))
    second: list[int] = sorted(parse_line(lines[1]))

    merged: list[int] = list(heapq.merge(first, second))

    print(merged)
    print(len(merged))


if __name__ == "__main__":
    main()
