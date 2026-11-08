MAXV = 9223372036854775807
MINV = -9223372036854775807 - 1


def main():
    xs = [MINV, 0, 0, 0, 0, 0, 0, 0]
    acc = MAXV
    for i in range(0, 8):
        acc += xs[i]
    print(acc)


main()
