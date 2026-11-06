BIG = 4611686018427387904

def main():
    xs = [BIG, BIG, -9223372036854775803]
    acc = 0
    for i in range(0, 3):
        acc += xs[i]
    print(acc)


main()
