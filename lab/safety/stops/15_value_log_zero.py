import math


def logarithm(value: float) -> float:
    return math.log(value)


print("prefix", logarithm(1.0))
print("e", logarithm(math.e))
print("next", logarithm(0.0))
