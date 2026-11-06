from ail.types import BigInt


def total(values: list[BigInt]) -> BigInt:
    running: BigInt = 0
    i = 0
    while i < len(values):
        running = running + values[i]
        i = i + 1
    return running


values: list[BigInt] = [1, 2, 2 ** 70, 2 ** 80]
print(total(values))
print(len(values))
