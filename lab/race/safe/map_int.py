"""Safe: ThreadPoolExecutor.map of a pure int function over int arguments."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    return (x * x + 3 * x + 7) % 1000003


def main():
    xs = list(range(64))
    with ThreadPoolExecutor(max_workers=4) as ex:
        got = list(ex.map(work, xs))
    total = 0
    for v in got:
        total += v
    print(len(got), total, got[0], got[63])


main()
