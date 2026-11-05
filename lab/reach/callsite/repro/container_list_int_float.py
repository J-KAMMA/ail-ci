# list[int] at one site, list[float] at another: total() returns int, then float.
def total(xs):
    s = 0
    for x in xs:
        s += x
    return s


print(total([1, 2, 3]))
print(total([0.5, 0.25]))
