from ail.types import BigInt


n: BigInt = 10 ** 30 + 7
q: BigInt = n // 3
r: BigInt = n % 3
mixed: BigInt = 7 * n // 10
negative: BigInt = n // -7
rem: BigInt = n % -7
print(q)
print(r)
print(mixed)
print(negative)
print(rem)
