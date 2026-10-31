def lcg(n: int) -> int:
    s = 12345
    t = 0
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        t = t + s // 65536
    return t


def lcg_big(n: int) -> int:
    s = 12345
    for i in range(n):
        s = s * 6364136223846793005 + 1442695040888963407
    return s


def collatz(n: int) -> int:
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps


def triangle(n: int) -> int:
    t = 0
    for i in range(n):
        t += i * (i + 1) // 2
    return t


def drift(n: int) -> int:
    x = 9223372036854775800
    for i in range(n):
        x += 1
    return x


def main():
    print(lcg(1000))
    print(lcg_big(20))
    print(collatz(27), collatz(97), collatz(871))
    print(triangle(3000))
    print(drift(5), drift(12))
    print(collatz(2 ** 70 + 1) if False else 0)


main()
