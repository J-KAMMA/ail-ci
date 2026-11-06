from ail.types import BigInt


wide: BigInt = 18446744073709551616
offset: BigInt = 18446744073709551611
small: int = wide - offset
print(wide)
print(small)
