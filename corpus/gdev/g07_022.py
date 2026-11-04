# task: Write a script that groups consecutive equal elements in a hardcoded list into sublists and prints the groups.
from itertools import groupby


def group_consecutive(items: list[int]) -> list[list[int]]:
    """Group consecutive equal elements into sublists."""
    return [list(group) for _, group in groupby(items)]


def main() -> None:
    data: list[int] = [1, 1, 2, 3, 3, 3, 4, 1, 1, 5, 5, 5, 5, 2, 2]
    groups: list[list[int]] = group_consecutive(data)
    print(f"Input: {data}")
    print(f"Number of groups: {len(groups)}")
    for index, group in enumerate(groups, start=1):
        print(f"Group {index}: {group}")


if __name__ == "__main__":
    main()
