import sys


SIZE = 15


def main() -> None:
    n = int(sys.stdin.readline().strip())
    steps = n * 20

    grid = [[0] * SIZE for _ in range(SIZE)]

    row = col = SIZE // 2
    # directions: 0=up, 1=right, 2=down, 3=left
    dr = (-1, 0, 1, 0)
    dc = (0, 1, 0, -1)
    facing = 0

    for _ in range(steps):
        if grid[row][col] == 0:
            facing = (facing + 1) % 4  # turn right
            grid[row][col] = 1
        else:
            facing = (facing - 1) % 4  # turn left
            grid[row][col] = 0
        row = (row + dr[facing]) % SIZE
        col = (col + dc[facing]) % SIZE

    black = 0
    out_lines = []
    for r in range(SIZE):
        line_chars = []
        for c in range(SIZE):
            if grid[r][c]:
                line_chars.append('#')
                black += 1
            else:
                line_chars.append('.')
        out_lines.append(''.join(line_chars))

    out_lines.append(str(black))
    sys.stdout.write('\n'.join(out_lines) + '\n')


if __name__ == "__main__":
    main()
