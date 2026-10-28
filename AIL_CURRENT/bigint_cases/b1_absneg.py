def neg_overflow():
    a = abs(-4611686018427387903)
    return a + 4611686018427387914


def neg_edge():
    a = abs(-4611686018427387904)
    return a


def neg_twice():
    a = abs(-4611686018427387904)
    return a * 2


def neg_small():
    a = abs(-3)
    return a + 1


def pos_overflow():
    a = abs(4611686018427387903)
    return a + 4611686018427387914


print(neg_overflow())
print(neg_edge())
print(neg_twice())
print(neg_small())
print(pos_overflow())
