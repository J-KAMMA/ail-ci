class Box:
    def __init__(self, v):
        self.v = v
    def grow(self, n):
        return self.v ** n
def powmod(b, e):
    return b ** e
def helper(n):
    return powmod(3, n) + 1
def top(n):
    return helper(n) * 2
def main():
    b = Box(7)
    print(b.grow(40))
    print(top(50))
    lst = [powmod(2, 70), powmod(2, 64) - 1]
    print(lst[0] + lst[1], lst[0] * lst[1], lst[0] // lst[1], lst[0] % lst[1])
    d = {"a": powmod(10, 30)}
    print(d["a"] - 1, -d["a"], abs(-d["a"]), d["a"] > 5, d["a"] == 10**30)
    s = 0
    for i in range(1, 30):
        s += powmod(i, 12)
    print(s)
    k = 1 << int("70")
    print(k, k >> 69, k.bit_length())
main()
