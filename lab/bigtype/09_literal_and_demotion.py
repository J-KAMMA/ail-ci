from ail.types import BigInt


wide: BigInt = 18446744073709551616
small: int = wide - 18446744073709551611
print(wide)
print(small)
