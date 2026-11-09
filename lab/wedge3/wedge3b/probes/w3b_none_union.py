class Rec:
    def __init__(self, base):
        self.t = []
        self.base = base

    def add(self, x):
        self.t.append(x)
        return None

    def score(self, x):
        return self.base + x

def group(tlist, flag=None):
    if flag:
        tlist.append(flag)
    return None

def classify(raw):
    out = []
    for key in raw:
        out.append((key, raw[key]))
    return out

def aggregate(rows):
    total = 0
    for k, v in rows:
        if isinstance(v, int):
            total += v
    return total

rec = Rec(10)
for i in range(5):
    group(rec.t, i)
    rec.add(i)
print('rec', rec.t, rec.score(3), rec.score(-2))
d = {'a': 1, 'b': 'x', 'c': 3}
print('classify', classify(d))
print('agg', aggregate([('a', 1), ('b', 'x'), ('c', 3)]))
print('none', group([], None), rec.add(9))
