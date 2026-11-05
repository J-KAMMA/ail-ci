# Recursion is excluded from propagation and cloning today (`recursive` in _signatures).
def power(x, n):
    if n == 0:
        return 1
    return x * power(x, n - 1)


print(power(3, 4))
print(power(1.5, 3))
