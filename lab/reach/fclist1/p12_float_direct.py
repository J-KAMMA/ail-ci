def scale(xs, n, k):
    i = 0
    while i < n:
        xs[i] = xs[i] * k
        i += 1


def run(n):
    xs = [0.0] * n
    i = 0
    while i < n:
        xs[i] = i * 0.5
        i += 1
    scale(xs, n, 3.0)
    return xs[n - 1] + xs[1]


def main():
    print(run(8))


main()
