"""Safe: ThreadPoolExecutor.map directly over a range (no intermediate list), results in order."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    return (x * x + 5 * x + 11) % 100003


def main():
    with ThreadPoolExecutor(max_workers=4) as ex:
        got = list(ex.map(work, range(10)))
    total = 0
    for v in got:
        total += v
    print(len(got), total, got[0], got[9])


main()
