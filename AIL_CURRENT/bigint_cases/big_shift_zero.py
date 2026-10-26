def f(a: int) -> int:
    return a << 64

class C:
    def __init__(self):
        self.v = 0

def h(v: int, n: int) -> int:
    return v << n

def main() -> None:
    print(f(1))
    print(0 << 63)
    print(0 << 64)
    print(0 << 100)
    print(0 << 1000)
    print(-1 << 63)
    print(1 << 62)
    print(0 >> 100)
    print(f(-1))
    xs = [0, -1]
    print(xs[0] << 100)
    print(xs[1] << 63)
    c = C()
    print(c.v << 200)
    d = {"v": 0}
    print(d["v"] << 300)
    print(h(0, 500))
    print(h(c.v, 64))
    cont()

def cont() -> None:
    xs = [-1 << 63]
    print(xs[0] - 1)
    d = {"k": -1 << 63}
    print(d["k"] * 2)
    t = (-1 << 63,)
    print(t[0] * 2)
    c = C()
    c.v = -1 << 63
    print(c.v * 2)
    v = -1 << 63
    ys = [v]
    print(ys[0] - 1)

main()
