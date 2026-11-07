def inc(xs, n):
    i = 0
    while i < n:
        xs[i] = xs[i] + 1
        i += 1


def main():
    a = [9223372036854775806, 1]
    inc(a, 2)
    print(a)
    inc(a, 2)
    print(a)


main()
