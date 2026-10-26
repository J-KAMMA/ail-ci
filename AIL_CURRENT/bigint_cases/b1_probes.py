import math


def via_arg(n):
    return n * n


def via_list(xs):
    return xs[0] + xs[1]


def via_dict(d):
    return d["k"] + d["k"]


class Box:
    def __init__(self, v):
        self.v = v

    def sq(self):
        return self.v * self.v


class ClassOnly:
    x = 3037000500

    def __init__(self):
        self.y = 1

    def sq(self):
        return self.x * self.x


def via_attr(o):
    return o.v * o.v


def aliased():
    a = 3037000500
    b = a
    return b * a


def boundaries():
    x = 2**62
    y = 1
    return x + y, -x - y, x * 2, (-x) * 2, x // 3, x % 7, (-x) // 7, (-x) % 7


def comb_perm():
    return (math.comb(1001, 1), math.comb(1001, 2), math.comb(66, 33), math.comb(68, 34),
            math.perm(20, 20), math.perm(21, 21), math.comb(0, 0), math.perm(0, 0), math.comb(1000, 0))


def small_len(s):
    return len(s) + 1


print(via_arg(3037000500))
print(via_arg(-3037000500))
print(via_list([3037000500, 3037000500]))
print(via_dict({"k": 3037000500}))
print(Box(3037000500).sq())
print(ClassOnly().sq())
print(via_attr(Box(3037000500)))
print(aliased())
print(boundaries())
print(comb_perm())
print(small_len("abc"))
