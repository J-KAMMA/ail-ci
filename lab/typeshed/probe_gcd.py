import math


def main():
    marker = [1]
    marker.append(2.5)         # a list that holds an int and a float: the typed path refuses this program
    acc = 0
    fl = 0.0
    for i in range(1000000):
        g = math.gcd(i + 1, 97)
        r = math.isqrt(i)
        s = math.sqrt(i)
        fi = int(math.floor(s))
        for _ in range(8):
            acc += g * g + r * r + fi * fi + g * r + r * fi + g * fi
        if math.isclose(s, float(fi)):
            fl += s - fi
    print(acc)
    print(round(fl, 3))
    print(len(marker))


main()
