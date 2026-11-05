import math


def root(value: float) -> float:
    return math.sqrt(value)


print("prefix", root(9.0))
print("fraction", root(0.25))
print("next", root(-1.0))
