"""CPython reference for matmul256: the same LCG fill and the same fixed order of design 3.5/3.7
(one block: lane k % 16 from -0.0, then the 8-4-2-1 tree), then the row-major sequential checksum."""


def fill(m, s):
    for i in range(256):
        for j in range(256):
            s = (1664525 * s + 1013904223) % 4294967296
            m[i][j] = s / 4294967296.0
    return s


def main():
    a = [[0.0] * 256 for _ in range(256)]
    b = [[0.0] * 256 for _ in range(256)]
    s = fill(a, 1)
    fill(b, s)
    c = [[0.0] * 256 for _ in range(256)]
    for i in range(256):
        for j in range(256):
            lane = [-0.0] * 16
            for k in range(256):
                lane[k % 16] += a[i][k] * b[k][j]
            w = 8
            while w:
                for x in range(w):
                    lane[x] += lane[x + w]
                w //= 2
            c[i][j] = lane[0]
    total = 0.0
    for i in range(256):
        for j in range(256):
            total += c[i][j]
    print("%.17g" % total)
    print("%.17g" % c[0][0])
    print("%.17g" % c[1][2])
    print("%.17g" % c[255][255])


main()
