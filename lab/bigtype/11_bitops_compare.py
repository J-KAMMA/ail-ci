from ail.types import BigInt


n: BigInt = 2 ** 80 + 12345
mask: BigInt = (1 << 80) - 1
low: BigInt = n & 0xFFFF
shifted: BigInt = n >> 40
delta: BigInt = n - (2 ** 80)
print(low)
print(shifted)
print(n > mask)
print(delta)
