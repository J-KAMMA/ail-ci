def power(base, e):
    return base ** e


def digits(n):
    return len(str(n))


def small_mod(n, m):
    acc = 0
    for i in range(n):
        acc = (acc * 31 + i) % m
    return acc


def main():
    print(power(7, 77))
    print(digits(power(3, 500)))
    print(small_mod(1000000, 1000003))
    print(1 << 100, (1 << 70) >> 3)
    x = int("123456789012345678901234567890")
    print(x * x, x % 1000, -x // 3)


main()
