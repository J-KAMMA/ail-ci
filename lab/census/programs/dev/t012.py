import sys


MOD: int = 1000003


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return
    n: int = int(data[0])
    nums: list[int] = [int(tok) for tok in data[1:1 + n]]

    product_all: int = 1
    product_nonzero: int = 1
    for x in nums:
        product_all = (product_all * (x % MOD)) % MOD
        if x != 0:
            product_nonzero = (product_nonzero * (x % MOD)) % MOD

    print(product_all, product_nonzero)


if __name__ == "__main__":
    main()
