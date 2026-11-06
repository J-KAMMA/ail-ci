from ail.types import BigInt


def double(value: BigInt) -> BigInt:
    return value * 2


def add(a: BigInt, b: BigInt) -> BigInt:
    return a + b


seed: BigInt = 2 ** 70
a: BigInt = double(seed)
b: BigInt = add(a, 21)
print(b)
