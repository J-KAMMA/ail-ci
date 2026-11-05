# C?-job-pre61-10241247-1: functools.partial with bound values
import functools

add = functools.partial(lambda a, b: a + b, 1)
print(add(2))
mul = functools.partial(lambda a, b: a * b, 6)
print(mul(7))

def f(a, b, c):
    return a * 100 + b * 10 + c

print(functools.partial(f, 1)(2, 3))
print(functools.partial(f, 1, 2)(3))
print(functools.partial(f, c=3)(1, 2))
