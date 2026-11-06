from ail.types import BigInt


def modpow(base: BigInt, exponent: BigInt, modulus: BigInt) -> BigInt:
    return pow(base, exponent, modulus)


p: BigInt = 2 ** 89 - 1
result: BigInt = modpow(3, p - 1, p)
modulus: BigInt = 10 ** 30 + 7
print(result)
print(pow(2, 200, modulus))
