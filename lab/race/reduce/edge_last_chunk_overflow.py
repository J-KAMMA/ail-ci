BIG = 4611686018427387904


def main():
    xs = [0] * 2000
    xs[1998] = BIG
    xs[1999] = BIG
    acc = 0
    for i in par_range(0, 2000):
        acc += xs[i]
    print(acc)


main()
