def f(x):
    return x * x

print(f(1.5))
print(f(*[3037000500]))

class P:
    def __init__(self, x):
        self.x = x
    def f(self):
        return self.x * self.x

print(P(1.5).f())
print(P(*[3037000500]).f())
