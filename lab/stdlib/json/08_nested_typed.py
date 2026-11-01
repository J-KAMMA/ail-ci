import json


def row_sum(row: list[int]) -> int:
    total = 0
    for value in row:
        total += value
    return total


def main() -> None:
    grid: list[list[int]] = json.loads("[[1, 2], [], [3, 4, 5]]")
    print(len(grid), [len(row) for row in grid])
    for row in grid:
        print(row_sum(row))
    scores: dict[str, int] = json.loads('{"alice": 10, "bob": 7}')
    print(json.dumps(scores, sort_keys=True))
    print(json.dumps(grid, indent=1))
    print(json.dumps(scores, separators=(",", ":"), sort_keys=True))
    print(json.dumps(grid, separators=(" ,", " = ")))


main()
