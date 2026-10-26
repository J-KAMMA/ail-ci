class L:
    def __len__(self):
        return 2 ** 60


class S:
    def __len__(self):
        return 7


class O:
    def __init__(self):
        self.l = L()


def direct():
    n = len(L())
    return n * 8


def via_arg(x):
    n = len(x)
    return n * 8


def via_item(xs):
    n = len(xs[0])
    return n * 8


def via_attr(o):
    n = len(o.l)
    return n * 8


def via_dict(d):
    n = len(d["x"])
    return n * 8


def builtin_len(s):
    return len(s) + 1


def small_custom(x):
    return len(x) + 1


print(direct())
print(via_arg(L()))
print(via_item([L()]))
print(via_attr(O()))
print(via_dict({"x": L()}))
print(builtin_len("abc"))
print(small_custom(S()))
print(len([1.5, 2.5]))
