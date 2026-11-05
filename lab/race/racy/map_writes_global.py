"""Racy: the function map runs writes a module global. The number of increments depends on
the schedule, so print only whether it moved and the length of the result list."""
from concurrent.futures import ThreadPoolExecutor

counter = 0


def work(x: int) -> int:
    global counter
    counter += 1
    return x * x


def main():
    with ThreadPoolExecutor(max_workers=4) as ex:
        got = list(ex.map(work, range(10)))
    print(len(got), counter > 0)


main()
