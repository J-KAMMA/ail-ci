"""Safe: three named submits in a with block, their results read in order after it."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    return x * x - 3 * x + 1


def main():
    with ThreadPoolExecutor(max_workers=3) as ex:
        f1 = ex.submit(work, 7)
        f2 = ex.submit(work, 9)
        f3 = ex.submit(work, 11)
    print(f1.result(), f2.result(), f3.result())


main()
