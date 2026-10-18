import sys


def main() -> None:
    commands = sys.stdin.readline().strip()

    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    dir_index = 0

    x, y = 0, 0
    visited: list[tuple[int, int]] = [(x, y)]

    for command in commands:
        if command == "L":
            dir_index = (dir_index - 1) % 4
        elif command == "R":
            dir_index = (dir_index + 1) % 4
        elif command == "F":
            dx, dy = directions[dir_index]
            x += dx
            y += dy
            visited.append((x, y))
        elif command == "B":
            dx, dy = directions[dir_index]
            x -= dx
            y -= dy
            visited.append((x, y))

    print(repr(visited[:10]))
    print(x == 0 and y == 0)


if __name__ == "__main__":
    main()
