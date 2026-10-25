class B:
    def __init__(self, v):
        self.v = v

    def bump(self):
        self.v *= self.v

    def add(self, x):
        self.v += x


class F:
    def __init__(self, v):
        self.v = v

    def scale(self):
        self.v *= 2.0

    def add(self, x):
        self.v += x


def bump_item(xs):
    xs[0] *= xs[0]


def bump_dict(d):
    d["k"] *= d["k"]


b = B(3037000500)
b.bump()
print(b.v)
xs = [3037000500]
bump_item(xs)
print(xs[0])
d = {"k": 3037000500}
bump_dict(d)
print(d["k"])
f = F(1.5)
f.scale()
f.add(0.5)
print(f.v)
c = B(4611686018427387904)
c.add(4611686018427387904)
print(c.v)
g = F(1.25)
g.add(2.5)
print(g.v)
