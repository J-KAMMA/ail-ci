class P:
    x = 3037000500
    def __init__(self, c):
        if c:
            self.x = 1.5
    def f(self):
        return self.x * self.x

print(P(False).f())
print(P(True).f())

def dflt(x=3037000500):
    return x * x

print(dflt())
print(dflt(1.5))

class Q:
    def __init__(self, x=3037000500):
        self.x = x
    def f(self):
        return self.x * self.x

print(Q(1.5).f())
print(Q().f())

class R:
    def __init__(self, x):
        self.x = x
    def f(self):
        return self.x * self.x

def h(v):
    return R(v).f()

def run(fn, v):
    return fn(v)

print(run(h, 3037000500))
print(h(1.5))
