"""Uneven parallel map: the last 1% of the items take 100 times as long as the rest."""
import multiprocessing

N = 500000
HEAVY_FROM = 495000


def work(x: int) -> int:
    v = x ^ 0x5A5A
    limit = 100
    if x >= HEAVY_FROM:
        limit = 10000
    k = 0
    while k < limit:
        v = (v * 1664525 + 1013904223) & 0x7FFFFFFF
        k += 1
    return v & 0xFFFF


def main():
    pool = multiprocessing.Pool(4)
    res = pool.map(work, range(N))
    pool.close()
    pool.join()
    total = 0
    for v in res:
        total += v
    print(len(res), total, res[0], res[N - 1])


if __name__ == "__main__":
    main()
