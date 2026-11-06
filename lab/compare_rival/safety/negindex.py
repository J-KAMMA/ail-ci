"""Safety probe 3: a negative index past the start of the list.  CPython raises IndexError."""
a = [1, 2, 3]
print(a[-5])
