def f(s):
    y = (s == s) + (s == s)
    for c in s:
        y = y * y
    return y


print(f("abcdefgh"))
