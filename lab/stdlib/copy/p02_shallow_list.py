import copy

def main() -> None:
    rows = [[1, 2], [3, 4]]
    grid = [rows, rows]
    shell = copy.copy(grid)
    shell.append("extra")
    shell[0].append(99)
    print(len(grid), len(shell))
    print(grid[0])
    print(shell[0])
    print(grid[0] is rows)
    print(shell[0] is shell[1])
    deep = copy.deepcopy(grid)
    deep[0].append(7)
    print(grid[0])
    print(deep[0])
    print(deep[0] is deep[1])

main()
