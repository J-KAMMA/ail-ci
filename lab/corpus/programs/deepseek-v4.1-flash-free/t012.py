import sys

MOD = 1000003


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    nums = [int(x) for x in data[1:1 + n]]

    product_all = 1
    product_nonzero = 1
    for x in nums:
        product_all = product_all * x % MOD
        if x != 0:
            product_nonzero = product_nonzero * x % MOD

    print(product_all)
    print(product_nonzero)


if __name__ == "__main__":
    main()
