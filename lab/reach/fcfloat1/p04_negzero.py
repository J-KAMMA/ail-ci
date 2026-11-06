import math


def neg(xs, n):
    i = 0
    while i < n:
        xs[i] = -xs[i]
        i += 1


def main():
    xs = [0.0, -0.0, 1.5]
    neg(xs, 3)
    print(repr(xs[0]), repr(xs[1]), repr(xs[2]))
    print(math.copysign(1.0, xs[0]), math.copysign(1.0, xs[1]))


main()
