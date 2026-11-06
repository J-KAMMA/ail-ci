from ail.types import BigInt


def fibonacci(n: int) -> BigInt:
    a: BigInt = 0
    b: BigInt = 1
    i = 0
    while i < n:
        c: BigInt = a + b
        a = b
        b = c
        i = i + 1
    return a


print(fibonacci(100))
