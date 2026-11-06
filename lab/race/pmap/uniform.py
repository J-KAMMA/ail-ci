"""Uniform-cost parallel map: every item does the same eight-round integer mix."""
import multiprocessing

N = 4000000


def work(x: int) -> int:
    v = (x * 2654435761) & 0x7FFFFFFF
    k = 0
    while k < 8:
        v = (v * 1103515245 + 12345) & 0x7FFFFFFF
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
