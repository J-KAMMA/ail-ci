MAXV = 9223372036854775807
MINV = -9223372036854775807 - 1


def main():
    xs = [MAXV]
    acc = MINV
    for i in par_range(0, 1):
        acc -= xs[i]
    print(acc)


main()
