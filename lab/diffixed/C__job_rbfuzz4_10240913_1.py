# C?-job-rbfuzz4-10240913-1: __hash__ call counts in dict methods
class K:
    count = 0
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        K.count += 1
        return hash(self.v)
    def __eq__(self, other):
        return isinstance(other, K) and self.v == other.v
    def __repr__(self):
        return "K(%r)" % self.v

k = K(1)
d = {k: "a"}
K.count = 0
print(d.pop(k), K.count)
d2 = {k: "a"}
K.count = 0
print(d2.setdefault(k, "b"), K.count)
e = {}
K.count = 0
print(e.pop(k, None), K.count)
d3 = {k: "a"}
K.count = 0
d3.update({k: "b"})
print(d3, K.count)
d4 = {k: "a"}
K.count = 0
print(d4.copy(), K.count)
d5 = {k: "a"}
K.count = 0
print(d5.popitem(), K.count)
d6 = {k: "a"}
K.count = 0
print(dict(d6), K.count)
