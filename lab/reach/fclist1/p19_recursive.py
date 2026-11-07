def perm(xs, k, n):
    if k == n:
        return 1
    c = 0
    i = k
    while i < n:
        t = xs[k]
        xs[k] = xs[i]
        xs[i] = t
        c += perm(xs, k + 1, n)
        t = xs[k]
        xs[k] = xs[i]
        xs[i] = t
        i += 1
    return c


def main():
    a = [3, 1, 2, 5]
    print(perm(a, 0, 4), a)


main()
