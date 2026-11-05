"""Safe boundary: a worker computes 2**63 from arithmetic. CPython prints the exact integer;
AIL may print it or stop loudly, but it must not print a different number."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    v = 1
    for i in range(0, 63):
        v = v * 2
    return v + x


def main():
    with ThreadPoolExecutor(max_workers=2) as ex:
        got = list(ex.map(work, [0, 1]))
    print(len(got), got[0], got[1])


main()
