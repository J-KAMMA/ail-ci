MAXV = 9223372036854775807


def main():
    xs = [1, 1, 1, 1, 1, 1, 1, 1, 1, MAXV]
    acc = 2
    for i in par_range(0, 10):
        acc += xs[i]
    print(acc)


main()
