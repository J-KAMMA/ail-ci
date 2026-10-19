import sys
from itertools import dropwhile, pairwise, takewhile


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return
    n: int = int(data[0])
    nums: list[int] = [int(tok) for tok in data[1:1 + n]]

    def below_fifty(x: int) -> bool:
        return x < 50

    taken: list[int] = list(takewhile(below_fifty, nums))
    dropped: list[int] = list(dropwhile(below_fifty, nums))
    diffs: list[int] = [b - a for a, b in pairwise(nums)]

    print(taken)
    print(dropped)
    print(diffs)


if __name__ == "__main__":
    main()
