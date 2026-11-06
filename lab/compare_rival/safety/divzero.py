"""Safety probe 4: division by zero in an expression.  CPython raises ZeroDivisionError."""
x = 10
y = 0
print(x // y)
