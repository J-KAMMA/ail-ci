def inc(n):
    return n + 1

def concat(a, b):
    return a + b

def scale(x):
    return x * 3

class Wrap:
    def __init__(self):
        self.n = 4

    def doubled(self):
        return self.n * 2

def run():
    w = Wrap()
    vals = [inc(1), inc(-1), concat('a', 'b'), concat('', 'x'), scale(2), scale(-5)]
    return vals, w.doubled()

vals, doubled = run()
print('vals', vals)
print('doubled', doubled)
print('jsonish', {'a': vals[0], 'b': vals[2]})
