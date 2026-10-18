import sys


def spiral_order(grid: list[str]) -> list[str]:
    if not grid or not grid[0]:
        return []
    result: list[str] = []
    top, bottom = 0, len(grid) - 1
    left, right = 0, len(grid[0]) - 1

    while top <= bottom and left <= right:
        for c in range(left, right + 1):
            result.append(grid[top][c])
        top += 1

        for r in range(top, bottom + 1):
            result.append(grid[r][right])
        right -= 1

        if top <= bottom:
            for c in range(right, left - 1, -1):
                result.append(grid[bottom][c])
            bottom -= 1

        if left <= right:
            for r in range(bottom, top - 1, -1):
                result.append(grid[r][left])
            left += 1

    return result


def main() -> None:
    data = sys.stdin.read().split()
    h = int(data[0])
    w = int(data[1])
    grid = data[2:2 + h]
    print("".join(spiral_order(grid)))


if __name__ == "__main__":
    main()
