import sys


def rule110(left: int, center: int, right: int) -> int:
    return (0b01101110 >> ((left << 2) | (center << 1) | right)) & 1


def next_generation(cells: list[int]) -> list[int]:
    size = len(cells)
    return [
        rule110(cells[(i - 1) % size], cells[i], cells[(i + 1) % size])
        for i in range(size)
    ]


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0]) if data else 0

    cells = [0] * 40
    cells[39] = 1

    for _ in range(n + 1):
        print("".join(map(str, cells)))
        cells = next_generation(cells)


if __name__ == "__main__":
    main()
