import math


def main():
    marker = [1]
    marker.append(2.5)         # forces the general path (a list holds one element kind)
    n = len("x" * 25)
    a = len("x" * 100)
    b = len("x" * 50)
    xs = [10 ** 9] * 3
    u = len("x" * 40)
    v = len("x" * 30)
    print(math.factorial(n))
    print(math.comb(a, b))
    print(math.prod(xs))
    print(math.lcm(2 ** u, 3 ** v))
    print(len(marker))


main()
