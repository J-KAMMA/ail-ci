class Counter:
    def __init__(self):
        self.n = 0


def fact(n):
    r = 1
    for i in range(1, n + 1):
        r = r * i
    return r


c = Counter()
c.n = fact(20)
print(c.n)
print("before the stop")
print(fact(25))
print("not reached")
