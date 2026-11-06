"""Safety probe 2: list index out of range inside a loop.  CPython prints 1 2 3 then raises IndexError."""
a = [1, 2, 3]
for i in range(5):
    print(a[i])
