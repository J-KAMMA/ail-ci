# C?-job-rbfuzz4-10240913-4: dict(d) __eq__ call count with a shared key table.
class K:
    count = 0

    def __init__(self, v):
        self.v = v

    def __hash__(self):
        return 1

    def __eq__(self, other):
        K.count += 1
        return self.v == other.v


d = {K(1): "a", K(2): "b", K(3): "c"}
K.count = 0
e = dict(d)
print(len(e), [e[k] for k in e], K.count)
