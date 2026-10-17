import sys
from typing import List


def count_subsets(values: List[int], target: int) -> int:
    m = len(values)
    total = 0
    for mask in range(1 << m):
        s = 0
        for i in range(m):
            if mask >> i & 1:
                s += values[i]
        if s == target:
            total += 1
    return total


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    t = int(data[1])
    values = [int(x) for x in data[2:2 + n]]
    values = values[:18]
    print(count_subsets(values, t))


if __name__ == "__main__":
    main()
