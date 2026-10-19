import math
import sys


def main() -> None:
    data = sys.stdin.read()

    # Directions in clockwise order starting from north (+y).
    directions: list[tuple[int, int]] = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    facing = 0  # index into directions; start facing north

    x, y = 0, 0
    visited: set[tuple[int, int]] = {(x, y)}
    max_dist_sq = 0

    for ch in data:
        if ch == "F":
            dx, dy = directions[facing]
            x, y = x + dx, y + dy
        elif ch == "B":
            dx, dy = directions[facing]
            x, y = x - dx, y - dy
        elif ch == "L":
            facing = (facing - 1) % 4
            continue
        elif ch == "R":
            facing = (facing + 1) % 4
            continue
        else:
            continue

        visited.add((x, y))
        dist_sq = x * x + y * y
        if dist_sq > max_dist_sq:
            max_dist_sq = dist_sq

    farthest = math.sqrt(max_dist_sq)

    print(len(visited))
    print(f"{farthest:.3f}")
    print(f"({x},{y})")


if __name__ == "__main__":
    main()
