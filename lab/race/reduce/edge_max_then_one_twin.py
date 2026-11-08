MAXV = 9223372036854775807


def main():
    xs = [0, 0, 0, 0, 0, 0, 0, 1]
    acc = MAXV
    for i in range(0, 8):
        acc += xs[i]
    print(acc)


main()
