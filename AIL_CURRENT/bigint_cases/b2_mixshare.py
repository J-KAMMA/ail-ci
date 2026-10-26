def build(k: int) -> int:
    x = 1
    while k > 0:
        x = x * 2
        k = k - 1
    return x

def sq(k: int) -> int:
    return k * k

def a(k: int) -> int:
    return 1 >> build(k)

def b(k: int) -> int:
    return -1 >> build(k)

def c(k: int) -> int:
    return -9223372036854775808 >> build(k)

def d(k: int) -> int:
    return sq(k) + 1

def e(k: int) -> int:
    return sq(k) + 2

print(a(70), b(70), c(70), d(5), e(6))
