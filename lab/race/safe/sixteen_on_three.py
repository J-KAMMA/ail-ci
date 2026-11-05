"""Safe: sixteen workers for only three items, so most workers have nothing to do."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    return x * 100 + 7


def main():
    xs = [2, 4, 6]
    with ThreadPoolExecutor(max_workers=16) as ex:
        got = list(ex.map(work, xs))
    print(len(got), got[0], got[1], got[2])


main()
