MAXV = 9223372036854775807


def main():
    xs = [MAXV, 1]
    acc = 1
    for i in range(0, 2):
        acc += xs[i]
    print(acc)


main()
