import math


def area(a, b):
    return a * b


def power(a, b):
    return a ** b


def through_list(xs):
    return xs[0] * xs[1]


def through_dict(d):
    return d["a"] * d["b"]


class P:
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def area(self):
        return self.a * self.b


p = P(3.5, 2.0)
print(area(3.5, 2.0))
print(power(2.0, 10.0))
print(through_list([3.5, 2.0]))
print(through_dict({"a": 3.5, "b": 2.0}))
print(p.area())
print(math.sqrt(9.0) * math.pi)
