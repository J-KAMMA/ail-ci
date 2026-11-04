import ail_array as ta


def fill(m: ta.Matrix[ta.f64], s: int) -> int:
    for i in range(256):
        for j in range(256):
            s = (1664525 * s + 1013904223) % 4294967296
            m[i, j] = float(s) / 4294967296.0
    return s


def main():
    a = ta.zeros((256, 256), ta.f64)
    b = ta.zeros((256, 256), ta.f64)
    s = fill(a, 1)
    fill(b, s)
    c = ta.matmul(a, b)
    total = 0.0
    for i in range(256):
        for j in range(256):
            total += c[i, j]
    print("%.17g" % total)
    print("%.17g" % c[0, 0])
    print("%.17g" % c[1, 2])
    print("%.17g" % c[255, 255])


main()
