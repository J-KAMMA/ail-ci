# C?-job-rbpre57-10271816-1: dict probing after delete+reinsert
class K:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        return self.v % 4
    def __eq__(self, other):
        log.append((self.v, getattr(other, "v", None)))
        return isinstance(other, K) and self.v == other.v

log = []
d = {K(i): i for i in range(6)}
del d[K(1)]
d[K(9)] = 9
d[K(1)] = 1
src = {K(i): i for i in range(6)}
print(d == src)
print(sorted(d.values()))
print(len(log))
copy = dict(d)
print(copy == src)
print(sorted(copy.keys(), key=lambda k: k.v)[0].v)
