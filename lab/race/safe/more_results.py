"""Safe: ten items for two workers, so the result list is longer than the worker count."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    return x * x


def main():
    xs = list(range(10))
    with ThreadPoolExecutor(max_workers=2) as ex:
        got = list(ex.map(work, xs))
    total = 0
    for v in got:
        total += v
    print(len(got), total, got[9])


main()
