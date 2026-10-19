import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    n = int(data[0])
    values = list(map(int, data[1:1 + n * n]))
    grid: list[list[int]] = [values[i * n:(i + 1) * n] for i in range(n)]

    diagonal_total = 0
    for i in range(n):
        diagonal_total += grid[i][i]
        diagonal_total += grid[i][n - 1 - i]
    if n % 2 == 1:
        # The centre cell lies on both diagonals and was counted twice.
        diagonal_total -= grid[n // 2][n // 2]

    max_row_sum = max((sum(row) for row in grid), default=0)

    print(diagonal_total)
    print(max_row_sum)


if __name__ == "__main__":
    main()
