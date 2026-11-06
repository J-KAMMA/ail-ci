"""Safety probe 1: int64 overflow in a loop.  CPython prints the exact big integer and exits 0."""
x = 1
for _ in range(50):
    x = x * 3
print(x)
