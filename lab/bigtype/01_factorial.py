from ail.types import BigInt


def factorial(n: int) -> BigInt:
    total: BigInt = 1
    i = 1
    while i <= n:
        total = total * i
        i = i + 1
    return total


print(factorial(30))
