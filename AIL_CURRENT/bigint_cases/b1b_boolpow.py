def f(s):
    y = (s == s) + (s == s)
    return y ** (y ** (y ** y))


print(f("a"))
