class Box:
    def __init__(self, v: int):
        self.v = v

x = 4000000000
xs = [4000000000]

def main():
    b = Box(4000000000)
    print(b.v * b.v)
    print(xs[0] * xs[0])
    print(x * x)
    print(int(9.3e18))
    y = -9223372036854775807 - 1
    print(y * -1)
main()
