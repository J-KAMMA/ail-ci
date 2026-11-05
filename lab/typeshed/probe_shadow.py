import math


def gcd(a, b):
    return a + b


def main():
    marker = [1]
    marker.append(2.5)         # forces the general path
    x = gcd(12, 8)
    y = math.gcd(12, 8)
    gcd_local = lambda a, b: a - b
    print(x, y, gcd_local(12, 8), len(marker))


main()
