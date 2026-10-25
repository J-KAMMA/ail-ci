class Acc:
    def __init__(self):
        self.x = 1
        self.log = []

    def step(self, i):
        self.x = self.x * 3 + i
        if i % 25 == 0:
            self.log.append(self.x % 1000003)


def main():
    a = Acc()
    for i in range(1, 101):
        a.step(i)
    print(a.x)
    print(a.log)
    big = a.x
    print(big > 2 ** 100, big // 10 ** 40, big % 97, -big // 7)
    d = {big: 1, big + 1: 2}
    print(d[big], d[a.x + 1], len(d))
    fib = [0, 1]
    for _ in range(200):
        fib.append(fib[-1] + fib[-2])
    print(fib[-1], sum(fib) % 1000000007, str(fib[-1])[:12], len(str(fib[-1])))
    print(sorted([fib[-1], -fib[-2], 5, fib[100]])[:2], max(fib), min(fib[3:]))


main()
