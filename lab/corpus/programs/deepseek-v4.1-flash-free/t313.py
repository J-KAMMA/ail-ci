import sys
from bisect import bisect_left


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print(0)
        print()
        return

    nums = [int(x) for x in data]
    n = len(nums)

    tails: list[int] = []
    tails_idx: list[int] = []
    parent: list[int] = [-1] * n

    for i, x in enumerate(nums):
        pos = bisect_left(tails, x)
        if pos == len(tails):
            tails.append(x)
            tails_idx.append(i)
        else:
            tails[pos] = x
            tails_idx[pos] = i
        parent[i] = tails_idx[pos - 1] if pos > 0 else -1

    length = len(tails)
    seq: list[int] = []
    k = tails_idx[-1]
    while k != -1:
        seq.append(nums[k])
        k = parent[k]
    seq.reverse()

    print(length)
    print(" ".join(map(str, seq)))


if __name__ == "__main__":
    main()
