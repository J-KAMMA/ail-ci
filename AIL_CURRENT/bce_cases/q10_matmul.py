import ail_array as ta


def fill(x: ta.Matrix[ta.f64], seed: int):
    r, c = x.shape
    s = seed
    for i in range(r):
        for j in range(c):
            s = (s * 1103515245 + 12345) % 2147483648
            x[i, j] = (s % 20001 - 10000) / 7.0


def main():
    a = ta.zeros((9, 17), ta.f64)
    b = ta.zeros((17, 5), ta.f64)
    fill(a, 1)
    fill(b, 2)
    c = ta.matmul(a, b)
    print(c[3, 4])


main()
