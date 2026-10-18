import sys


def main() -> None:
    n = int(input())
    nums: list[int] = [int(tok) for tok in input().split()]
    nums = nums[:n]

    print(*nums, sep=', ', end='\n')

    for num in nums:
        sys.stdout.write(f"{num}\n")

    print(*nums, sep='|')


if __name__ == "__main__":
    main()
