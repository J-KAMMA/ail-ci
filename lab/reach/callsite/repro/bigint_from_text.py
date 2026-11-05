# An int instance fed a value beyond int64 from int(text): must stop loudly or match, never wrap.
import sys


def twice(x):
    return x * 2


print(twice(2.5))
print(twice(int("4611686018427387904")))
