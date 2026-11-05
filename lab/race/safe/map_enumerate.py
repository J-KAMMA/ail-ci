"""Safe: the map iterator consumed by enumerate in a for loop with an (i, v) target."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    return (x * 7 + 2) % 89


def main():
    xs = list(range(9))
    total = 0
    with ThreadPoolExecutor(max_workers=2) as ex:
        for i, v in enumerate(ex.map(work, xs)):
            total += i * v
    print(len(xs), total)


main()
