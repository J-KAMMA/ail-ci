import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print(0)
        return

    n = int(data[0])
    t = int(data[1])
    nums = [int(x) for x in data[2:2 + n]][:18]

    # Map each achievable sum to the number of index subsets producing it.
    ways: dict[int, int] = {0: 1}
    for x in nums:
        new_ways = dict(ways)
        for s, c in ways.items():
            new_ways[s + x] = new_ways.get(s + x, 0) + c
        ways = new_ways

    print(ways.get(t, 0))


if __name__ == "__main__":
    main()
