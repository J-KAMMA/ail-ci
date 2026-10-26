def build(k: int) -> int:
    x = 1
    while k > 0:
        x = x * 2
        k = k - 1
    return x

def one(a: int) -> int:
    t = -1
    for i in range(9223372036854775806, a):
        t = i
        if t == 9223372036854775807:
            break
    return t

def one_explicit(a: int) -> int:
    t = -1
    for i in range(9223372036854775806, a, 1):
        t = i
        if t == 9223372036854775807:
            break
    return t

def exact() -> int:
    t = -1
    for i in range(9223372036854775806, 9223372036854775807):
        t = i
    return t

def empty(a: int) -> int:
    t = -1
    for i in range(a, a + 1):
        t = i
    return t

def step2(a: int) -> int:
    for i in range(9223372036854775806, a, 2):
        if i > 9223372036854775807:
            return i
    return -1

def neg(a: int) -> int:
    t = 0
    for i in range(-9223372036854775807, a, -1):
        t = i
        if t == -9223372036854775808:
            break
    return t

def plus_one() -> int:
    t = -1
    for i in range(9223372036854775806, 9223372036854775807 + 1):
        t = i
    return t

def plus_one_step() -> int:
    t = -1
    for i in range(9223372036854775806, 9223372036854775807 + 1, 1):
        t = i
    return t

a = build(70)
print(one(a), one_explicit(a), exact(), empty(-9223372036854775807), step2(a), neg(-a))
print(plus_one(), plus_one_step())
