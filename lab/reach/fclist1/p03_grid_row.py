def setfirst(row, v):
    row[0] = v


def main():
    grid = [[0] * 3 for _ in range(3)]
    i = 0
    while i < 3:
        setfirst(grid[i], i + 7)
        i += 1
    print(grid)


main()
