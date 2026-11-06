from concurrent.futures import ThreadPoolExecutor


def sq(x: int) -> int:
    return x * x


def main():
    with ThreadPoolExecutor(max_workers=4) as ex:
        acc = sum(ex.map(sq, range(10)))
    print(acc)


main()
