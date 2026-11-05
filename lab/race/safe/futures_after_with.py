"""Safe: futures submitted inside the with block, their results read after it; results in order."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    return (x * 2654435761) % 1000000007


def main():
    xs = list(range(10))
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(work, x) for x in xs]
    total = 0
    for f in futs:
        total += f.result()
    print(len(futs), total)


main()
