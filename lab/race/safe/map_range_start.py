"""Safe: ThreadPoolExecutor.map over range(start, stop) bound in a name, summed after the map."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    return x * 3 - 7


def main():
    lo = 5
    hi = 25
    with ThreadPoolExecutor(max_workers=3) as ex:
        got = list(ex.map(work, range(lo, hi)))
    total = 0
    for i, v in enumerate(got):
        total += i + v
    print(len(got), total, got[0], got[19])


main()
