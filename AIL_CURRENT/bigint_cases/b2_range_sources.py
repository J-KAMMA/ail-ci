def build(k: int) -> int:
    x = 1
    while k > 0:
        x = x * 2
        k = k - 1
    return x

class B:
    def __init__(self, n: int):
        self.stop: int = n

def via_list(xs) -> int:
    t = -1
    for i in range(9223372036854775806, xs[0]):
        t = i
        if t == 9223372036854775807:
            break
    return t

def via_attr(b: B) -> int:
    t = -1
    for i in range(9223372036854775806, b.stop):
        t = i
        if t == 9223372036854775807:
            break
    return t

def via_dict(d) -> int:
    t = -1
    for i in range(9223372036854775806, d["stop"]):
        t = i
        if t == 9223372036854775807:
            break
    return t

def via_alias(n: int) -> int:
    m = n
    k = m
    t = -1
    for i in range(9223372036854775806, k):
        t = i
        if t == 9223372036854775807:
            break
    return t

big = build(70)
print(via_list([big]), via_attr(B(big)), via_dict({"stop": big}), via_alias(big))
