import sys


MOD = 998244353


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    numbers = [int(x) for x in data[1:1 + n]]

    product = 1
    for value in numbers:
        product *= value

    print(product)
    print(product % MOD)


if __name__ == "__main__":
    main()
