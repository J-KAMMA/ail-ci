def build() -> int:
    a = 1
    b = 2
    c = 3
    d = 4
    e = 5
    f = 6
    g = 7
    h = 8
    i = 9
    return a + b + c + d + e + f + g + h + i

def a(xs: list[int], i: int) -> int:
    return build()

def b(xs: list[int], i: int) -> int:
    return build()

def risky(xs: list[int], i: int) -> int:
    return xs[i]

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(a([1, 2, 3], 1), b([1, 2, 3], 1), risky([1, 2, 3], 1))
main()
