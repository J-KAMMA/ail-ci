import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print("none")
        return

    n = int(data[0])
    nums = [int(x) for x in data[1:1 + n]]

    values: set[int] = set(nums)
    # For a < b with a + b == 0, a must be negative and b == -a.
    pairs = sorted((a, -a) for a in values if a < 0 and -a in values)

    if not pairs:
        print("none")
        return

    for a, b in pairs:
        print(f"{a} {b}")


if __name__ == "__main__":
    main()
