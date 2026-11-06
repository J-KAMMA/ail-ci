def main():
    acc = 0
    neg = 0
    for i in par_range(0, 100):
        acc += i
        neg -= i
    print(acc, neg)


main()
