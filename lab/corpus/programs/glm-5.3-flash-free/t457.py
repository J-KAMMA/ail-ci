import sys


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    nums = [int(tok) for tok in data[1 : 1 + n]]
    for x in nums:
        # One line per number using a wide variety of f-string format specs.
        print(
            f"width={x:12d} "
            f"fill={x:0>12} "
            f"sign={x:+d} "
            f"hex={x:#x} "
            f"binary={x:#b} "
            f"percent={x / 100:.0%} "
            f"exponent={x:.3e} "
            f"comma={x:,}"
        )


if __name__ == "__main__":
    main()
