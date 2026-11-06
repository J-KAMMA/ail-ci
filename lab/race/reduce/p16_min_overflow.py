BIG = 4611686018427387904

def main():
    xs = [-BIG, -BIG, -1]
    acc = 0
    for i in par_range(0, 3):
        acc += xs[i]
    print(acc)


main()
