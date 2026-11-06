import math


def put(xs, n):
    xs[0] = math.inf
    xs[1] = -math.inf
    xs[2] = math.nan
    xs[3] = xs[0] - xs[0]
    xs[4] = 1e308 * 10.0


def main():
    xs = [0.0, 0.0, 0.0, 0.0, 0.0]
    put(xs, 5)
    i = 0
    while i < 5:
        print(repr(xs[i]), xs[i] == xs[i])
        i += 1


main()
