class Box:
    pass


def one(x):
    return round(x)


def assigned(x):
    y = round(x)
    return y


def through_list(x):
    d = {"r": round(x)}
    return d["r"]


def through_attr(x):
    o = Box()
    o.r = round(x)
    return o.r


def safe_defined():
    return 1


def safe_call():
    return safe_defined()


def safe_split(s):
    parts = s.split()
    return parts[0]


def safe_len():
    n = len("abcd")
    return n + 1


print(one(1e300))
print(assigned(1e300))
print(through_list(1e300))
print(through_attr(1e300))
print(safe_call(), safe_split("a b"), safe_len())
