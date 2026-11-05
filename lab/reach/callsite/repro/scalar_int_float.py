# One unannotated def called with int at one site and float at another.
# CPython: 3 / 3.5 / 7 / 3.5. An int instance and a float instance are needed; int must stay int.
def add(a, b):
    return a + b


def half(x):
    return x // 2 if isinstance(x, int) else x / 2


print(add(1, 2))
print(add(1.5, 2))
print(half(7) + add(2, 2))
print(half(7.0))
