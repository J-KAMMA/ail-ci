from ail.types import BigInt


def largest(values: list[BigInt]) -> BigInt:
    best: BigInt = values[0]
    i = 1
    while i < len(values):
        if values[i] > best:
            best = values[i]
        i = i + 1
    return best


values: list[BigInt] = [2 ** 40, 2 ** 70, 2 ** 65]
print(largest(values))
print(sum(values))
