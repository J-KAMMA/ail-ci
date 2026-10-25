class Acc:
    def __init__(self):
        self.x = 1
        self.log = []
    def step(self, i):
        self.x = self.x * 3 + i
def main():
    a = Acc()
    for i in range(1, 80):
        a.step(i)
    print(a.x)
    fib = [0, 1]
    for _ in range(150):
        fib.append(fib[-1] + fib[-2])
    print(fib[-1], str(fib[-1]), fib[-1] > fib[-2], int(float(fib[10])))
    d = {fib[-1]: "big"}
    print(d[fib[-1]], list(d)[0] % 1000)
main()
