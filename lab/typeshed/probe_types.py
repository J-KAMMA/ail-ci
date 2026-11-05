import bisect
import math
import random


def main():
    a = math.floor(2.5)
    b = math.sqrt(4)
    c = math.isqrt(10 ** 18)
    xs = [1, 3, 5, 7]
    d = bisect.bisect_left(xs, 4)
    random.seed(1)
    e = random.random()
    print(a, b, c, d, round(e, 6))


main()
