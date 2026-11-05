"""Safe: exactly one worker and more items than it takes at once."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    return (x * 5) % 97


def main():
    xs = list(range(12))
    with ThreadPoolExecutor(max_workers=1) as ex:
        got = list(ex.map(work, xs))
    total = 0
    for v in got:
        total += v
    print(len(got), total, got[0], got[11])


main()
