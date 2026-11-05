"""Safe: ThreadPoolExecutor.map of a pure float function, results added after the map."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> float:
    return float(x) / 4.0 + 0.5


def main():
    xs = list(range(50))
    with ThreadPoolExecutor(max_workers=3) as ex:
        got = list(ex.map(work, xs))
    total = 0.0
    for v in got:
        total += v
    print(len(got), round(total, 6), round(got[0], 6), round(got[49], 6))


main()
