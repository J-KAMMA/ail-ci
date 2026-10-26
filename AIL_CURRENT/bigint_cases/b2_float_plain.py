x = 1.5
y = 2.25
vals = [3.5, 4.25]

class Pair:
    def __init__(self):
        self.f: float = 5.5

def add(u, v):
    return u + v

def from_list():
    return vals[0] * vals[1]

def from_attr(p: Pair):
    return p.f / x

def from_dict(d):
    return d["f"] - y

print(x + y, x * y, x / y)
print(add(x, y), from_list(), from_attr(Pair()), from_dict({"f": 9.75}))
