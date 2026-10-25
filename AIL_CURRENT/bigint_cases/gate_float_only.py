class P:
    def __init__(self, a, b):
        self.a = a
        self.b = b
    def area(self):
        return self.a * self.b
d = {'a': 3.5, 'b': 2.0}
xs = [3.5, 2.0]
p = P(3.5, 2.0)
print(d['a'] * d['b'])
print(xs[0] * xs[1])
print(p.area())
