import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    nums = [int(x) for x in data]
    ranks = {value: rank for rank, value in enumerate(sorted(set(nums)))}
    out = "\n".join(f"{n} {ranks[n]}" for n in nums)
    sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
