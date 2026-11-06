"""Safety probe 5: 100000 levels of recursion.  CPython raises RecursionError at the default limit."""


def f(n):
    if n == 0:
        return 0
    return 1 + f(n - 1)


print(f(100000))
