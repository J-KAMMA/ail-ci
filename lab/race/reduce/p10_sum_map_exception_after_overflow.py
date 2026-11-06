BIG = 4611686018427387904

from concurrent.futures import ThreadPoolExecutor


def f(x: int) -> int:
    if x == 3:
        return 1000 // (x - 3)
    return BIG


def main():
    acc = 0
    try:
        with ThreadPoolExecutor(max_workers=3) as ex:
            acc = sum(ex.map(f, range(5)))
    except ZeroDivisionError:
        print("caught ZeroDivisionError", acc)
    print(acc)


main()
